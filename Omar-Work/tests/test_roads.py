import io
import json
from urllib.parse import urlsplit, parse_qs, unquote
import numpy as np
import pandas as pd
import pytest
from fillinq.roads import RoadNetwork, RoadRoutingError
from fillinq.territories import compact_sectors
from fillinq.config import OpsConfig
from fillinq.routing import plan_routes


def road_server(calls):
    def request(req, timeout):
        calls.append(req.full_url)
        url = urlsplit(req.full_url)
        coords = [list(map(float, point.split(','))) for point in unquote(url.path.rsplit('/',1)[-1]).split(';')]
        if '/table/' in url.path:
            query=parse_qs(url.query)
            sources=[int(x) for x in query['sources'][0].split(';')]
            destinations=[int(x) for x in query['destinations'][0].split(';')]
            distances=[[0 if i==j else 5000 + i*100+j*10 for j in destinations] for i in sources]
            data=dict(code='Ok',distances=distances,durations=[[x/10 for x in row] for row in distances],
                sources=[dict(location=coords[i],distance=5) for i in sources],destinations=[dict(location=coords[i],distance=5) for i in destinations])
        else:
            data=dict(code='Ok',routes=[dict(legs=[dict(distance=5000,duration=500,steps=[dict(geometry=dict(coordinates=[a,[a[0],b[1]],b]))]) for a,b in zip(coords,coords[1:])])])
        return io.StringIO(json.dumps(data))
    return request


def test_road_matrix_is_directional_cached_and_never_derived_from_aerial_distance(tmp_path):
    calls=[]
    road=RoadNetwork(cache_path=tmp_path/'roads.sqlite',opener=road_server(calls),sleep=lambda seconds:None)
    km, seconds, access=road.matrix([49.14,49.141],[9.2,9.201])
    assert km[0,1] == 5.01 and km[1,0] == 5.1
    assert seconds[0,1] == 501
    assert access[0][2] == 5
    assert road.access(49.14,9.2)['roadLatitude'] == 49.14
    another=RoadNetwork(cache_path=tmp_path/'roads.sqlite',opener=lambda *a,**k:pytest.fail('cached streets should not be requested again'))
    again,_,_=another.matrix([49.141,49.14,49.14],[9.201,9.2,9.2])
    assert again[0,1] == km[1,0] and again[1,2] == 0
    assert len(calls)==1


def test_street_geometry_preserves_all_ordered_legs_and_road_metrics(tmp_path):
    calls=[]
    road=RoadNetwork(cache_path=tmp_path/'roads.sqlite',opener=road_server(calls),sleep=lambda seconds:None)
    legs=road.route([(49.14,9.2),(49.15,9.21),(49.14,9.2)])
    assert len(legs)==2
    assert legs[0]['points']==[[49.14,9.2],[49.15,9.2],[49.15,9.21]]
    assert legs[0]['distanceKm']==5 and legs[0]['drivingSeconds']==500
    assert 'continue_straight=false' in calls[0]


def test_network_or_geometry_failure_has_no_straight_line_fallback(tmp_path):
    def failed(*args,**kwargs): raise OSError('offline')
    road=RoadNetwork(cache_path=tmp_path/'offline.sqlite',opener=failed)
    with pytest.raises(RoadRoutingError,match='no straight-line'):
        road.matrix([49.1,49.2],[9.1,9.2])
    road=RoadNetwork(cache_path=tmp_path/'geometry.sqlite',opener=lambda *a,**k:io.StringIO(json.dumps(dict(code='Ok',routes=[dict(legs=[dict(steps=[],distance=5,duration=2)])]))))
    with pytest.raises(RoadRoutingError,match='geometry is missing'):
        road.route([(49.1,9.1),(49.2,9.2)])


def test_colocated_yard_and_unloading_have_a_valid_zero_length_road_leg(tmp_path):
    road=RoadNetwork(cache_path=tmp_path/'zero.sqlite',opener=lambda *a,**k:io.StringIO(json.dumps(dict(code='Ok',routes=[dict(legs=[dict(steps=[],distance=0,duration=0)])]))))
    legs=road.route([(49.1,9.1),(49.1,9.1)])
    assert legs==[dict(points=[[49.1,9.1],[49.1,9.1]],distanceKm=0,drivingSeconds=0)]


def test_large_matrices_are_batched_without_duplicate_provider_coordinates(tmp_path):
    calls=[]
    road=RoadNetwork(cache_path=tmp_path/'large.sqlite',opener=road_server(calls),sleep=lambda seconds:None)
    matrix,_,_=road.matrix([49+i/1000 for i in range(101)],[9]*101)
    assert matrix.shape==(101,101) and len(calls)==9
    assert all(len(unquote(urlsplit(url).path.rsplit('/',1)[-1]).split(';'))<=100 for url in calls)


def test_long_street_routes_keep_all_legs_across_provider_request_boundaries(tmp_path):
    calls=[]
    road=RoadNetwork(cache_path=tmp_path/'long-route.sqlite',opener=road_server(calls),sleep=lambda seconds:None)
    points=[(49+i/1000,9+i/1000) for i in range(201)]
    legs=road.route(points)
    assert len(legs)==200 and len(calls)==3
    for index,leg in enumerate(legs):
        assert leg['points'][0]==list(points[index])
        assert leg['points'][-1]==list(points[index+1])
    assert all(len(unquote(urlsplit(url).path.rsplit('/',1)[-1]).split(';'))<=100 for url in calls)


def sector_stops(n=24):
    angles=np.linspace(-np.pi,np.pi,n,endpoint=False)
    return pd.DataFrame([dict(site=f's{i:02}',lat=49.14+.04*np.sin(angle),lon=9.2+.06*np.cos(angle),
        vol_l=1000,kg=350,n_bins=1,must=True,value=.9) for i,angle in enumerate(angles)])


class StreetFixture:
    max_snap_m=1000
    def matrix(self,lat,lon):
        lat,lon=np.array(lat),np.array(lon)
        km=np.hypot((lat[:,None]-lat[None,:])*111,(lon[:,None]-lon[None,:])*73)*1.5
        return km,km/30*3600,[(a,b,0) for a,b in zip(lat,lon)]


def test_sectors_are_contiguous_and_trucks_keep_the_same_area_across_loads():
    cfg=OpsConfig(depot_lat=49.14,depot_lon=9.2,disposal_lat=49.14,disposal_lon=9.2,truck_payload_t=1,max_vehicles=4)
    cfg.road_network=StreetFixture()
    stops=sector_stops()
    km,seconds,_=cfg.road_network.matrix([cfg.depot_lat,*stops.lat,cfg.disposal_lat],[cfg.depot_lon,*stops.lon,cfg.disposal_lon])
    sectors=compact_sectors(stops,4,cfg,seconds,km)
    assert len(set(sectors))==4
    # Every label has a single run around the circle, including the circular seam.
    for label in set(sectors):
        flags=sectors==label
        assert np.count_nonzero(flags & ~np.roll(flags,1))==1

    plan=plan_routes(stops,cfg,time_limit_s=1)
    assert not plan.dropped_mandatory
    ownership={}
    for route in plan.routes:
        served=[site for trip in route['trips'] for site in trip['stops']]
        assert route['hours']<=cfg.shift_hours
        assert len(route['trips'])>=2
        indices=[int(site[1:]) for site in served]
        for index in indices:ownership[index]=route['truck']
        assert all(trip['weight_t']<=cfg.truck_payload_t for trip in route['trips'])
    ordered=np.array([ownership[i] for i in range(len(stops))])
    assert len(ownership)==len(stops)
    for truck in set(ordered):
        flags=ordered==truck
        assert np.count_nonzero(flags & ~np.roll(flags,1))==1


def test_street_access_and_actual_road_time_can_reject_an_aerially_nearby_stop():
    class RestrictedRoads(StreetFixture):
        def matrix(self,lat,lon):
            km, seconds, access=super().matrix(lat,lon)
            for i, la in enumerate(lat):
                if la==49.15: access[i]=(la,lon[i],1500)
                if la==49.16:
                    seconds[i,:]=40000; seconds[:,i]=40000; seconds[i,i]=0
            return km,seconds,access
    cfg=OpsConfig(depot_lat=49.14,depot_lon=9.2,disposal_lat=49.14,disposal_lon=9.2,max_vehicles=1)
    cfg.road_network=RestrictedRoads()
    stops=pd.DataFrame([dict(site=site,lat=lat,lon=9.2,vol_l=1000,kg=350,n_bins=1,must=True,value=1)
                        for site,lat in [('NO_ROAD',49.15),('SLOW_ROAD',49.16),('OK',49.141)]])
    plan=plan_routes(stops,cfg,time_limit_s=1)
    assert set(plan.dropped_mandatory)=={'NO_ROAD','SLOW_ROAD'}
    assert plan.reasons['NO_ROAD']=='road_unreachable'
    assert plan.reasons['SLOW_ROAD']=='exceeds_shift'
    assert [site for route in plan.routes for site,_,_ in route['stops']]==['OK']
