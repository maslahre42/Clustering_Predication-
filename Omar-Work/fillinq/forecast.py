"""Fill-rate model and overflow-risk forecast.

Model (per filling cycle i of container c):
    daily fill rate  R_i  ~  LogNormal( a_c + b_month + g * vacation_share , sigma^2 )
    fill after d days = min(100, R_i * d)

* a_c   container effect, shrunk towards its material mean (partial pooling,
        so containers with few readings borrow strength from similar ones)
* b_m   month-of-year effect (seasonality), g = school-vacation effect
* Readings of 100 / "overfull" are censored (true fill >= 100) and are handled
  with the censored likelihood instead of being treated as exact values.

Everything is estimated by maximum a-posteriori with an analytic gradient
(scipy L-BFGS), so it runs in about a second on the full dataset.
"""
from __future__ import annotations
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

from .calendar_features import vacation_fraction, DAILY

B_SD = 0.30   # prior sd of month effects
G_SD = 0.70   # prior sd of vacation effect


class RateModel:
    def __init__(self, sigma_grid=(0.45, 0.6, 0.75, 0.9, 1.05)):
        self.sigma_grid = sigma_grid
        self.fitted = False

    # ------------------------------------------------------------------ fit
    def fit(self, intervals: pd.DataFrame) -> "RateModel":
        iv = intervals.reset_index(drop=True)
        self.containers = np.array(sorted(iv["container"].unique()))
        self.materials = np.array(sorted(iv["material"].unique()))
        cidx = {c: i for i, c in enumerate(self.containers)}
        midx = {m: i for i, m in enumerate(self.materials)}
        c = iv["container"].map(cidx).to_numpy()
        cm = (iv.drop_duplicates("container").set_index("container")["material"]
              .reindex(self.containers).map(midx).to_numpy())
        month = iv["end"].dt.month.to_numpy() - 1
        v = vacation_fraction(iv["start"], iv["end"])
        y = np.log(iv["rate"].to_numpy())
        cens = iv["censored"].to_numpy()
        nC, nM = len(self.containers), len(self.materials)
        n_per = np.bincount(c, minlength=nC)

        def make_obj(sigma, tau):
            def obj(theta):
                a = theta[:nC]; m = theta[nC:nC + nM]
                b = theta[nC + nM:nC + nM + 12]; g = theta[-1]
                mu = a[c] + b[month] + g * v
                z = (y - mu) / sigma
                logsf = norm.logsf(z)
                ll = np.where(cens, logsf, -0.5 * z ** 2 - np.log(sigma))
                dmu = np.where(cens, np.exp(norm.logpdf(z) - logsf) / sigma, z / sigma)
                da = a - m[cm]
                P = (-0.5 * np.sum((da / tau) ** 2) - 0.5 * np.sum((b / B_SD) ** 2)
                     - 0.5 * (g / G_SD) ** 2)
                f = -(ll.sum() + P)
                ga = -(np.bincount(c, dmu, nC) - da / tau ** 2)
                gm = -np.bincount(cm, da / tau ** 2, nM)
                gb = -(np.bincount(month, dmu, 12) - b / B_SD ** 2)
                gg = -(np.sum(dmu * v) - g / G_SD ** 2)
                return f, np.concatenate([ga, gm, gb, [gg]])
            return obj

        start_a = np.full(nC, np.log(np.median(iv["rate"])))
        theta0 = np.concatenate([start_a, np.full(nM, start_a[0]), np.zeros(12), [0.0]])

        # step 1: weak prior, pick sigma by profile likelihood
        best = None
        for s in self.sigma_grid:
            res = minimize(make_obj(s, 1.0), theta0, jac=True, method="L-BFGS-B")
            ll_only = self._loglik(res.x, nC, nM, c, cm, month, v, y, cens, s)
            if best is None or ll_only > best[0]:
                best = (ll_only, s, res.x)
        _, sigma, theta = best
        # step 2: estimate tau from the spread of container effects, refit
        a_hat = theta[:nC]
        se2 = sigma ** 2 / np.maximum(n_per, 1)
        tau = float(np.sqrt(max(np.var(a_hat) - np.mean(se2), 0.05 ** 2)))
        tau = float(np.clip(tau, 0.15, 1.2))
        res = minimize(make_obj(sigma, tau), theta, jac=True, method="L-BFGS-B")
        theta = res.x

        self.sigma, self.tau = float(sigma), tau
        self.a = theta[:nC]
        self.m = theta[nC:nC + nM]
        self.b = theta[nC + nM:nC + nM + 12]
        self.g = float(theta[-1])
        self.n_int = n_per
        self.cidx, self.midx = cidx, midx
        self.container_mat = cm
        self.var_a = 1.0 / (n_per / sigma ** 2 + 1.0 / tau ** 2)
        self.fitted = True
        return self

    @staticmethod
    def _loglik(theta, nC, nM, c, cm, month, v, y, cens, sigma):
        a = theta[:nC]; b = theta[nC + nM:nC + nM + 12]; g = theta[-1]
        mu = a[c] + b[month] + g * v
        z = (y - mu) / sigma
        return float(np.where(cens, norm.logsf(z), -0.5 * z ** 2 - np.log(sigma)).sum())

    # -------------------------------------------------------------- predict
    def _mu_and_s(self, containers, start, target):
        containers = np.asarray(containers)
        start = pd.DatetimeIndex(pd.to_datetime(start))
        target = pd.DatetimeIndex(pd.to_datetime(target))
        idx = np.array([self.cidx.get(x, -1) for x in containers])
        known = idx >= 0
        a = np.where(known, self.a[np.where(known, idx, 0)], np.nan)
        var_a = np.where(known, self.var_a[np.where(known, idx, 0)], self.tau ** 2)
        if (~known).any():  # unseen container: fall back to the material mean
            mats = pd.Series(containers).str.split("|").str[-1].map(self.midx)
            mean_m = np.where(mats.notna(), self.m[mats.fillna(0).astype(int).to_numpy()], self.m.mean())
            a = np.where(known, a, mean_m)
        month = target.month.to_numpy() - 1
        vac = vacation_fraction(start, target)
        mu = a + self.b[month] + self.g * vac
        s = np.sqrt(self.sigma ** 2 + var_a)
        days = np.maximum((target - start).days.to_numpy(), 0).astype(float)
        return mu, s, days

    def predict(self, containers, last_empty, target, thresholds=(70, 90, 100)) -> pd.DataFrame:
        """Expected fill and P(fill >= T) when collected on `target`,
        given the container was last emptied on `last_empty`."""
        mu, s, days = self._mu_and_s(containers, last_empty, target)
        ld = np.log(np.maximum(days, 0.5))
        m = mu + ld
        L = np.log(100.0)
        mean = np.exp(m + s ** 2 / 2) * norm.cdf((L - m - s ** 2) / s) + 100.0 * norm.sf((L - m) / s)
        out = pd.DataFrame({"container": np.asarray(containers), "days": days, "mean_fill": mean})
        for T in thresholds:
            out[f"p_ge_{T}"] = norm.sf((np.log(T) - m) / s)
        return out

    def fill_quantile(self, containers, last_empty, target, q=0.5):
        """Quantile q of the fill level (capped at 100) when collected on `target`."""
        mu, s, days = self._mu_and_s(containers, last_empty, target)
        z = norm.ppf(q)
        return np.minimum(100.0, np.exp(mu + np.log(np.maximum(days, 0.5)) + s * z))

    def days_to_full(self, containers, last_empty, q=0.5):
        """Days after `last_empty` until the container reaches 100% (quantile q of time)."""
        mu, s, _ = self._mu_and_s(containers, last_empty, last_empty)
        # use month effect of the last_empty date as a first approximation
        z = norm.ppf(1 - q)
        return np.exp(np.log(100.0) - mu - s * z)

    # -------------------------------------------------------- tables / info
    def container_table(self) -> pd.DataFrame:
        t = pd.DataFrame({
            "container": self.containers,
            "site": [x.split("|")[0] for x in self.containers],
            "material": [x.split("|")[1] for x in self.containers],
            "log_rate": self.a,
            "rate_pct_per_day": np.exp(self.a),
            "intervals": self.n_int,
            "days_to_full_median": 100.0 / np.exp(self.a),
        })
        return t

    def seasonality_table(self) -> pd.DataFrame:
        return pd.DataFrame({"month": range(1, 13), "multiplier": np.exp(self.b - self.b.mean())})

    def summary(self) -> dict:
        return {
            "sigma": self.sigma, "tau": self.tau,
            "vacation_multiplier": float(np.exp(self.g)),
            "material_rate_pct_per_day": {m: float(np.exp(v)) for m, v in zip(self.materials, self.m)},
        }

    def daily_log_rate(self, container_index: np.ndarray, days: pd.DatetimeIndex) -> np.ndarray:
        """Matrix [n_containers, n_days] of expected daily log-rate (for the simulator)."""
        month = days.month.to_numpy() - 1
        vac = DAILY["vacation"].reindex(days.normalize()).fillna(0).to_numpy()
        season = self.b[month] + self.g * vac
        return self.a[container_index][:, None] + season[None, :]


# ---------------------------------------------------------------- validation
def _score(model: RateModel, test: pd.DataFrame, train: pd.DataFrame) -> dict:
    pred = model.predict(test["container"], test["start"], test["end"], thresholds=(70, 100))
    obs = test["fill"].to_numpy()
    # baselines
    med_mat = train.groupby("material")["rate"].median()
    med_con = train.groupby("container")["rate"].median()
    base_mat = np.minimum(100, test["material"].map(med_mat).fillna(train["rate"].median()).to_numpy() * test["gap"].to_numpy())
    r_con = test["container"].map(med_con).fillna(test["material"].map(med_mat)).fillna(train["rate"].median())
    base_con = np.minimum(100, r_con.to_numpy() * test["gap"].to_numpy())
    need = (obs >= 70).astype(int)
    res = {
        "n_test": int(len(test)),
        "MAE_model": float(np.mean(np.abs(pred["mean_fill"].to_numpy() - obs))),
        "MAE_material_median": float(np.mean(np.abs(base_mat - obs))),
        "MAE_container_median": float(np.mean(np.abs(base_con - obs))),
        "MAE_always_mean": float(np.mean(np.abs(obs.mean() - obs))),
    }
    if 0 < need.sum() < len(need):
        res["AUC_need>=70_model"] = float(roc_auc_score(need, pred["p_ge_70"]))
        res["AUC_need>=70_days_since_last_visit"] = float(roc_auc_score(need, test["gap"]))
        res["AUC_need>=70_container_median"] = float(roc_auc_score(need, base_con))
    return res


def cross_validate(intervals: pd.DataFrame, k: int = 5, seed: int = 0) -> pd.DataFrame:
    """k-fold CV over filling cycles (calendar effects can be learnt from other folds)."""
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, k, len(intervals))
    rows = []
    for f in range(k):
        tr, te = intervals[fold != f], intervals[fold == f]
        model = RateModel().fit(tr)
        rows.append(_score(model, te, tr))
    return pd.DataFrame(rows)


def forward_test(intervals: pd.DataFrame, cutoff: str = "2026-04-01") -> dict:
    """Train on cycles ending before `cutoff`, test on later ones (no leakage;
    seasonality of unseen months can not be learnt, so this is the hard test)."""
    tr = intervals[intervals["end"] < cutoff]
    te = intervals[intervals["end"] >= cutoff]
    model = RateModel().fit(tr)
    out = _score(model, te, tr)
    out["train_until"] = cutoff
    return out
