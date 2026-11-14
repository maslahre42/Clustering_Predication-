import os
import unittest
import numpy as np
import pandas as pd

from src.distance_provider import ModularDistanceProvider
from src.clustering import (
    audit_collection_reset_evidence,
    extract_container_profiles,
    evaluate_cluster_stability,
    cluster_containers
)
from src.predictor import (
    predict_container_demands,
    validate_fill_predictor,
    _count_bw_holiday_days_between
)
from src.optimizer import (
    align_demands_and_coordinates,
    select_smart_collection_candidates,
    solve_gurobi_waste_vrp,
    verify_gurobi_routes,
    simulate_baseline_fixed_schedule,
    simulate_greedy_nearest_neighbor,
    run_experiment_a_same_containers,
    compare_baseline_vs_dynamic
)


class TestAuditCompliance(unittest.TestCase):
    """
    Comprehensive verification test suite verifying all 5 Priorities of the Technical Audit
    and the 500 €/truck-day (8.0h shift = 62.50 €/h) municipal cost framework.
    """

    @classmethod
    def setUpClass(cls):
        cls.demands_path = "data/predicted_demands.csv"
        cls.coords_path = "data/heilbronn_actual_glass_containers.csv"
        cls.cleaned_path = "data/cleaned_fill_levels.csv"

        assert os.path.exists(cls.demands_path), f"Missing {cls.demands_path}"
        assert os.path.exists(cls.coords_path), f"Missing {cls.coords_path}"

        cls.demands_df = pd.read_csv(cls.demands_path)
        cls.coords_df = pd.read_csv(cls.coords_path)
        if os.path.exists(cls.cleaned_path):
            cls.cleaned_df = pd.read_csv(cls.cleaned_path)
        else:
            cls.cleaned_df = pd.read_csv("glass_fill_levels_anonymized_f.csv")

    # -------------------------------------------------------------------------
    # PRIORITY 1: DATA ALIGNMENT TESTS
    # -------------------------------------------------------------------------
    def test_align_demands_and_coordinates_one_to_one(self):
        """Tests that align_demands_and_coordinates performs deterministic 1-to-1 merge."""
        merged = align_demands_and_coordinates(self.demands_df, self.coords_df)
        self.assertEqual(len(merged), len(self.coords_df))
        self.assertTrue(merged["Location_id"].is_unique)
        self.assertTrue(merged["latitude"].notna().all())
        self.assertTrue(merged["longitude"].notna().all())
        self.assertTrue(merged["predicted_fill_perc"].notna().all())

    def test_align_demands_shuffle_invariance(self):
        """Tests that shuffling row orders in input DataFrames produces identical mappings."""
        shuffled_demands = self.demands_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        shuffled_coords = self.coords_df.sample(frac=1.0, random_state=99).reset_index(drop=True)

        res_standard = align_demands_and_coordinates(self.demands_df, self.coords_df)
        res_shuffled = align_demands_and_coordinates(shuffled_demands, shuffled_coords)

        pd.testing.assert_frame_equal(
            res_standard.sort_values("Location_id").reset_index(drop=True),
            res_shuffled.sort_values("Location_id").reset_index(drop=True)
        )

    # -------------------------------------------------------------------------
    # PRIORITY 3: GEOGRAPHIC DISTANCE PROVIDER TESTS
    # -------------------------------------------------------------------------
    def test_distance_provider_raises_on_missing_coordinates(self):
        """Tests that ModularDistanceProvider raises ValueError when a container ID cannot be resolved."""
        bad_ids = ["NON_EXISTENT_BIN_99999"]
        with self.assertRaises(ValueError):
            ModularDistanceProvider(
                location_ids=bad_ids,
                real_coords_df=self.coords_df,
                mode="osrm"
            )

    def test_distance_provider_assert_finite_coordinates(self):
        """Tests that invalid/infinite GPS coordinates raise ValueError."""
        with self.assertRaises(ValueError):
            ModularDistanceProvider.assert_finite_coordinates(np.nan, 9.21)
        with self.assertRaises(ValueError):
            ModularDistanceProvider.assert_finite_coordinates(49.14, 999.0)

    def test_distance_provider_matrix_finiteness_and_mode_info(self):
        """Tests that distance and duration matrices are strictly non-negative and finite."""
        candidates = select_smart_collection_candidates(self.demands_df, self.coords_df, target_count=10)
        dp = ModularDistanceProvider(real_coords_df=candidates, mode="osrm")

        self.assertTrue(np.isfinite(dp.dist_matrix_km).all())
        self.assertTrue((dp.dist_matrix_km >= 0.0).all())
        self.assertTrue(np.isfinite(dp.duration_matrix_min).all())
        self.assertTrue((dp.duration_matrix_min >= 0.0).all())

        info = dp.get_active_mode_info()
        self.assertIn("mode", info)
        self.assertIn("routing_profile", info)
        self.assertEqual(info["num_bins"], 10)

    # -------------------------------------------------------------------------
    # PRIORITY 4: MODEL & ECONOMICS & AUDITOR TESTS
    # -------------------------------------------------------------------------
    def test_gurobi_8h_shift_and_cost_accounting(self):
        """Tests Gurobi CVRP solver with 8.0h shift limit and 500 €/day cost accounting."""
        candidates = select_smart_collection_candidates(self.demands_df, self.coords_df, target_count=24)
        dp = ModularDistanceProvider(real_coords_df=candidates, mode="osrm")

        routes_df, solver_info = solve_gurobi_waste_vrp(
            candidates_df=candidates,
            dist_provider=dp,
            max_shift_hours=8.0,
            truck_daily_cost_eur=500.0,
            time_limit_sec=20,
            return_solver_info=True
        )

        self.assertFalse(routes_df.empty)
        self.assertIn("solver_info", routes_df.attrs)
        self.assertEqual(solver_info["hourly_rate_eur"], 62.50)
        self.assertEqual(solver_info["available_fleet_limit"], 4)
        self.assertLessEqual(routes_df["shift_hours"].max(), 8.0)
        self.assertTrue((routes_df["daily_charter_cost_eur"] == 500.0).all())

        # Test independent route auditor
        audit_res = verify_gurobi_routes(
            routes_df=routes_df,
            candidates_df=candidates,
            dist_provider=dp,
            max_shift_hours=8.0
        )
        self.assertTrue(audit_res["all_checks_passed"])
        self.assertEqual(audit_res["verified_unique_stops"], 24)

    # -------------------------------------------------------------------------
    # PRIORITY 5: PREDICTION & CLUSTERING TESTS
    # -------------------------------------------------------------------------
    def test_clustering_ari_stability_across_seeds(self):
        """Tests that Adjusted Rand Index (ARI) cluster stability across seeds exceeds 0.85."""
        profiles = extract_container_profiles(self.cleaned_df, material_filter="white")
        stability = evaluate_cluster_stability(profiles, n_clusters=4, seeds=(42, 7, 123, 999, 2026))

        self.assertGreater(stability["mean_pairwise_ari"], 0.85)
        self.assertGreater(stability["min_pairwise_ari"], 0.80)

    def test_clustering_flexible_tier_naming(self):
        """Tests that cluster_containers assigns unique, non-repeating tier names for arbitrary k."""
        profiles = extract_container_profiles(self.cleaned_df, material_filter="white")
        for k in (3, 4, 6):
            clust_df, _ = cluster_containers(profiles, n_clusters=k)
            self.assertEqual(clust_df["tier"].nunique(), k)

    def test_predictor_dual_semantics_and_interval_holidays(self):
        """Tests continuous_sensor vs collection_visit_reset semantics and interval holidays."""
        profiles = extract_container_profiles(self.cleaned_df, material_filter="white")

        pred_reset = predict_container_demands(
            profiles, days_ahead=2, data_semantics="collection_visit_reset"
        )
        pred_sensor = predict_container_demands(
            profiles, days_ahead=2, data_semantics="continuous_sensor"
        )

        self.assertIn("urgency_status", pred_reset.columns)
        self.assertIn("demand_volume_m3", pred_reset.columns)
        self.assertIn("demand_weight_kg", pred_reset.columns)
        # Continuous sensor adds to current fill, whereas reset accumulates from residual
        self.assertFalse(np.array_equal(pred_reset["predicted_fill_perc"], pred_sensor["predicted_fill_perc"]))

        # Holiday exposure test
        h_count = _count_bw_holiday_days_between(
            pd.Timestamp("2025-12-23"), pd.Timestamp("2026-01-02")
        )
        self.assertGreater(h_count, 0)

    def test_predictor_separated_uncensored_and_censored_evaluation(self):
        """Tests validate_fill_predictor reports uncensored MAE/RMSE and overfull recall."""
        metrics, test_df = validate_fill_predictor(self.cleaned_df, material_filter="white")
        self.assertIn("uncensored_mae", metrics)
        self.assertIn("uncensored_rmse", metrics)
        self.assertIn("urgent_recall_pct", metrics)
        self.assertIn("overfull_recall_pct", metrics)
        self.assertIn("mae_improvement_pct", metrics)
        self.assertGreater(metrics["mae_improvement_pct"], 0.0)

    # -------------------------------------------------------------------------
    # PRIORITY 2: EXPERIMENT A & EXPERIMENT B EXECUTION
    # -------------------------------------------------------------------------
    def test_experiments_a_and_b_execute_and_produce_valid_results(self):
        """Tests execution and structure of Experiment A and Experiment B."""
        aligned = align_demands_and_coordinates(self.demands_df, self.coords_df)
        candidates = select_smart_collection_candidates(self.demands_df, self.coords_df, target_count=24)
        dp_candidates = ModularDistanceProvider(real_coords_df=candidates, mode="osrm")

        routes_df = solve_gurobi_waste_vrp(
            candidates_df=candidates,
            dist_provider=dp_candidates,
            max_shift_hours=8.0,
            truck_daily_cost_eur=500.0,
            time_limit_sec=20
        )

        # Experiment A
        exp_a_df = run_experiment_a_same_containers(
            candidates_df=candidates,
            dist_provider=dp_candidates,
            dynamic_routes_df=routes_df,
            max_shift_hours=8.0,
            truck_daily_cost_eur=500.0
        )
        self.assertFalse(exp_a_df.empty)
        self.assertEqual(len(exp_a_df), 5)
        self.assertIn("Gurobi Optimal CVRP", exp_a_df.columns)
        self.assertIn("Unoptimized Fixed-Order Route", exp_a_df.columns)

        # Experiment B (Full 109 containers)
        dp_full = ModularDistanceProvider(real_coords_df=aligned, mode="osrm")
        base_109_kpis = simulate_baseline_fixed_schedule(
            containers_df=aligned,
            dist_provider=dp_full,
            max_shift_hours=8.0,
            truck_daily_cost_eur=500.0
        )
        self.assertEqual(base_109_kpis["num_containers_visited"], 109)

        exp_b_df = compare_baseline_vs_dynamic(
            baseline_kpis=base_109_kpis,
            dynamic_routes_df=routes_df,
            dynamic_candidates_df=candidates,
            truck_daily_cost_eur=500.0,
            max_shift_hours=8.0
        )
        self.assertFalse(exp_b_df.empty)
        self.assertIn("Metric (Experiment B: Policy Comparison)", exp_b_df.columns)
        self.assertIn("Fixed-Schedule Sweep", exp_b_df.columns)
        self.assertIn("Dynamic Gurobi AI Policy", exp_b_df.columns)


if __name__ == "__main__":
    unittest.main()
