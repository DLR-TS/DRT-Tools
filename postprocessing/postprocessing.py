# -*- coding: utf-8 -*-
""" Command line interface to process SUMO output files.

Created on Tue Dec 08 11:04:00 2020

@author: ritz_ph
@author: rumm_jo
"""

import os
import sys
import pathlib

import click
import numpy as np
import xlwt

try:
    from lxml import etree
except ImportError:
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
        except ImportError:
            print("Failed to import ElementTree from any known place")

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")
# SUMO modules
import traci  # noqa


def get_root(path):
    """Get root from XML file in path."""
    path = pathlib.Path(path)
    try:
        tree = etree.parse(path.as_posix())
    except Exception as error_loading:
        raise IOError(f"Error loading file {path.as_posix()}.") from error_loading
    root = tree.getroot()
    return root


def process_dispatchinfo(file):
    """
    Process data of dispatchinfo output file.

    Parameters
    ----------
    file : str
        Path of dispatchinfo file.

    Raises
    ------
    Exception
        Error loading file.

    Returns
    -------
    dispatch_dict : dict
        Relevant output variables.

    """

    root_dispatchinfo = get_root(file)
    n_persons = 0
    timeloss_rel = []
    timeloss_abs = []
    n_trips = len(root_dispatchinfo)
    if n_trips == 0:
        # no dispatchinfo entries
        return None
    for dispatch_shared in root_dispatchinfo:
        n_persons += len(dispatch_shared.get("persons").split(" "))
        n_persons += len(dispatch_shared.get("sharingPersons").split(" "))
        timeloss_rel.append(dispatch_shared.get("relLoss"))
        timeloss_rel.append(dispatch_shared.get("relLoss2"))
        timeloss_abs.append(dispatch_shared.get("absLoss"))
        timeloss_abs.append(dispatch_shared.get("absLoss2"))
    dispatch_dict = {
        "n_trips": n_trips,
        "n_persons": n_persons,
        "timeloss_rel": np.array(timeloss_rel, dtype=float),
        "timeloss_abs": np.array(timeloss_abs, dtype=float)}
    return dispatch_dict


def process_direct_routes(file):
    """
    Process data of direct routes file.

    Parameters
    ----------
    file : str
        Path of direct route file.

    Raises
    ------
    Exception
        Error loading file.

    Returns
    -------
    direct_route_dict : dict
        Relevant output variables.

    """

    root_direct_route = get_root(file)
    n_persons = 0
    travel_time = []
    route_length = []
    list_vehicles = root_direct_route.findall("vehicle")  # skip vehicle info (is not needed)
    list_routes = [veh.find("route") for veh in list_vehicles]
    n_routes = len(list_routes)
    if n_routes == 0:
        # no direct route entries
        return None
    for route in list_routes:
        travel_time.append(route.get("cost"))
        route_length.append(route.get("routeLength"))
    direct_route_dict = {
        "n_routes": n_routes,
        "travel_time": np.array(travel_time, dtype=float),
        "route_length": np.array(route_length, dtype=float)}
    return direct_route_dict


def process_tripinfo(tripinfo_path, vtype='drt',
                     depart_earliest=-1, arrival_latest=-1):
    """
    Process data of tripinfo output file.

    Parameters
    ----------
    tripinfo_path : str
        Path of tripinfo file.
    vtype: str, optional
        Only tripinfos with this vehicle type are considered.
        The default is 'drt'.
    depart_earliest: float, optional
        Skip personinfo entry which depart earlier than this.
        The default is -1, which means no filtering.
    arrival_latest: float, optional
        Skip personinfo entry which arrive later than this.
        The default is -1, which means no filtering.

    Raises
    ------
    Exception
        Error loading file.

    Returns
    -------
    tripinfo_dict : dict
         Relevant output variables.

    """

    root_tripinfo = get_root(tripinfo_path)
    list_personinfo = root_tripinfo.findall("personinfo")
    list_tripinfo = root_tripinfo.findall(f"tripinfo[@vType='{vtype}']")

    if len(list_tripinfo) == 0:
        raise Exception(f"There is no tripinfo entry with vType='{vtype}'.")

    if len(list_personinfo) == 0:
        raise Exception("There is no personinfo entry.")

    timeloss_ride = []
    duration_ride = []
    waiting_ride = []
    length_ride = []
    duration_walk = []
    length_walk = []
    duration_trip = []
    stoptime_trip = []
    length_trip = []
    occupied_distance_trip = []
    occupied_time_trip = []

    n_personinfo_raw = len(list_personinfo)
    n_filtered = 0  # filtered personinfo
    n_walking_only = 0  # personinfo without ride

    for personinfo in list_personinfo:

        # Filter for time window
        if depart_earliest > 0:
            if float(personinfo.get('depart')) < depart_earliest:
                n_filtered += 1
                continue
        if arrival_latest > 0:
            arrivals = [float(entry.get('arrival')) for entry in personinfo]
            if max(arrivals) > arrival_latest:
                n_filtered += 1
                continue

        list_ride = personinfo.findall("ride")
        list_walk = personinfo.findall("walk")

        if list_walk and not list_ride:
            n_walking_only += 1

        skip = False
        for ride in list_ride:
            # skip personinfo with depart < 0
            if float(ride.get("depart")) < 0:
                skip = True
                break
            # skip personinfo with arrival < 0
            if float(ride.get("arrival")) < 0:
                skip = True
                break
            # skip personinfo with routeLength < 0
            if float(ride.get("routeLength")) < 0:
                skip = True
                break
            # skip personinfo with vehicle "NULL"
            if ride.get("vehicle") == "NULL":
                skip = True
                break
            timeloss_ride.append(ride.get("timeLoss"))
            duration_ride.append(ride.get("duration"))
            waiting_ride.append(ride.get("waitingTime"))
            length_ride.append(ride.get("routeLength"))

        if skip:
            n_filtered += 1
            continue

        for walk in list_walk:
            duration_walk.append(walk.get("duration"))
            length_walk.append(walk.get("routeLength"))

    for tripinfo in list_tripinfo:
        duration_trip.append(tripinfo.get("duration"))
        stoptime_trip.append(tripinfo.get("stopTime"))
        length_trip.append(tripinfo.get("routeLength"))
        for trip in tripinfo:
            occupied_distance_trip.append(trip.get("occupiedDistance"))
            occupied_time_trip.append(trip.get("occupiedTime"))

    rate_filtered = n_filtered/n_personinfo_raw

    duration_ride_sum = np.array(duration_ride, dtype=float).sum()
    time_occupied_sum = np.array(occupied_time_trip, dtype=float).sum()
    duration_trip_sum = np.array(duration_trip, dtype=float).sum()
    time_stop_sum = np.array(stoptime_trip, dtype=float).sum()
    time_driving_sum = duration_trip_sum - time_stop_sum

    passengers_per_time_occupied = duration_ride_sum / time_occupied_sum
    passengers_per_time_driving = duration_ride_sum / time_driving_sum

    tripinfo_dict = {
        "n_personinfo_raw": n_personinfo_raw,
        "n_filtered": n_filtered,
        "rate_filtered": rate_filtered,
        "n_walking_only": n_walking_only,
        "n_rides": len(duration_ride),
        "n_vehicles":  len(duration_trip),
        "n_walks": len(duration_walk),
        "timeloss_ride":  np.array(timeloss_ride, dtype=float),
        "duration_ride":  np.array(duration_ride, dtype=float),
        "waiting_ride":  np.array(waiting_ride, dtype=float),
        "length_ride":  np.array(length_ride, dtype=float),
        "duration_walk":  np.array(duration_walk, dtype=float),
        "length_walk": np.array(length_walk, dtype=float),
        "duration_trip": np.array(duration_trip, dtype=float),
        "stoptime_trip": np.array(stoptime_trip, dtype=float),
        "length_trip": np.array(length_trip, dtype=float),
        "occupied_distance_trip": np.array(
            occupied_distance_trip, dtype=float),
        "occupied_time_trip": np.array(occupied_time_trip, dtype=float),
        "passengers_per_time_occupied": passengers_per_time_occupied,
        "passengers_per_time_driving": passengers_per_time_driving
    }

    return tripinfo_dict


def calculate_stats(tripinfo_dict, dispatch_dict, direct_routes_dict):
    """Calculate statistics for common KPIs."""
    # Rides
    # counts personinfo with ride and arrival > 0 only
    n_rides = tripinfo_dict["n_rides"]
    if dispatch_dict:
        n_trips_pooling = dispatch_dict["n_trips"]
        n_persons_pooling = dispatch_dict["n_persons"]
        rate_pooling = n_persons_pooling / n_rides
        n_trips = n_rides - n_persons_pooling + n_trips_pooling
        requests_per_trip = n_rides / n_trips
    else:
        n_trips_pooling = -1
        n_persons_pooling = -1
        rate_pooling = -1
        n_trips = -1
        requests_per_trip = -1

    if direct_routes_dict:
        n_direct_routes = direct_routes_dict["n_routes"]
        direct_travel_time_mean = direct_routes_dict["travel_time"].mean()/60  # in minutes
        direct_route_length_sum = direct_routes_dict["route_length"].sum()/1000  # in km
        direct_route_length_mean = direct_routes_dict["route_length"].mean()/1000  # in km
    else:
        n_direct_routes = -1
        direct_travel_time_mean = -1
        direct_route_length_sum = -1
        direct_route_length_mean = -1

    waiting_ride_mean = tripinfo_dict["waiting_ride"].mean()/60
    waiting_ride_std = tripinfo_dict["waiting_ride"].std()/60
    distance_ride = tripinfo_dict["length_ride"].sum()/1000
    distance_ride_mean = tripinfo_dict["length_ride"].mean()/1000
    duration_ride_mean = tripinfo_dict["duration_ride"].mean()/60

    if dispatch_dict:
        timeloss_rel_mean = dispatch_dict["timeloss_rel"].mean()
        timeloss_rel_max = dispatch_dict["timeloss_rel"].max()
    else:
        timeloss_rel_mean = -1
        timeloss_rel_max = -1

    # Walks
    n_walks = tripinfo_dict["n_walks"]
    distance_walk_mean = tripinfo_dict["length_walk"].mean()/1000
    duration_walk_mean = tripinfo_dict["duration_walk"].mean()/60
    duration_trip_mean = duration_ride_mean + 2 * duration_walk_mean

    # Vehicle trips
    n_vehicles = tripinfo_dict["n_vehicles"]

    distance_vehicle = tripinfo_dict["length_trip"].sum()/1000
    distance_vehicle_mean = tripinfo_dict["length_trip"].mean()/1000
    distance_vehicle_occupied = tripinfo_dict[
        "occupied_distance_trip"].sum()/1000
    distance_vehicle_occupied_mean = tripinfo_dict[
        "occupied_distance_trip"].mean()/1000
    distance_vehicle_empty = distance_vehicle - distance_vehicle_occupied

    duration_vehicle = tripinfo_dict["duration_trip"].sum()/60
    duration_vehicle_occupied = tripinfo_dict["occupied_time_trip"].sum()/60
    duration_vehicle_occupied_mean = tripinfo_dict[
        "occupied_time_trip"].mean()/60
    duration_vehicle_stop = tripinfo_dict["stoptime_trip"].sum()/60
    duration_vehicle_stop_mean = tripinfo_dict["stoptime_trip"].mean()/60
    duration_vehicle_driving = duration_vehicle - duration_vehicle_stop

    output_dict = {
        "n_personinfo_raw": tripinfo_dict["n_personinfo_raw"],
        "n_filtered": tripinfo_dict["n_filtered"],
        "rate_filtered": tripinfo_dict["rate_filtered"],
        "n_walking_only": tripinfo_dict["n_walking_only"],
        "n_rides": n_rides,
        "n_trips": n_trips,
        "requests_per_trip": requests_per_trip,
        "n_trips_pooling": n_trips_pooling,
        "n_persons_pooling": n_persons_pooling,
        "rate_pooling": rate_pooling,
        "waiting_ride_mean": waiting_ride_mean,
        "waiting_ride_std": waiting_ride_std,
        "distance_ride": distance_ride,
        "distance_ride_mean": distance_ride_mean,
        "duration_ride_mean": duration_ride_mean,
        "duration_trip_mean": duration_trip_mean,
        "timeloss_rel_mean": timeloss_rel_mean,
        "timeloss_rel_max": timeloss_rel_max,
        "n_walks": n_walks,
        "distance_walk_mean": distance_walk_mean,
        "duration_walk_mean": duration_walk_mean,
        "n_vehicles": n_vehicles,
        "distance_vehicle": distance_vehicle,
        "distance_vehicle_mean": distance_vehicle_mean,
        "distance_vehicle_occupied": distance_vehicle_occupied,
        "distance_vehicle_occupied_mean": distance_vehicle_occupied_mean,
        "duration_vehicle_driving": duration_vehicle_driving,
        "duration_vehicle_occupied": duration_vehicle_occupied,
        "duration_vehicle_occupied_mean": duration_vehicle_occupied_mean,
        "distance_vehicle_empty": distance_vehicle_empty,
        "duration_vehicle_stop_mean": duration_vehicle_stop_mean,
        "passengers_per_time_occupied": tripinfo_dict[
            "passengers_per_time_occupied"],
        "passengers_per_time_driving": tripinfo_dict[
            "passengers_per_time_driving"],
        "n_direct_routes": n_direct_routes,
        "direct_travel_time_mean": direct_travel_time_mean,
        "direct_route_length_mean": direct_route_length_mean,
        "operational_efficiency": distance_ride/distance_vehicle,
        "system_efficiency": direct_route_length_sum/distance_vehicle
    }

    return output_dict


def dict2xls(output_file, output_dict):
    """
    Write output_dict to Excel 97 file.

    Parameters
    ----------
    output_file : str
        Name of Excel file.
    output_dict : dict
        Output dictionary.

    Returns
    -------
    None.

    """

    workbook = xlwt.Workbook()
    worksheet = workbook.add_sheet("output")

    row = 0
    for key, value in output_dict.items():
        worksheet.write(row, 0, key)
        worksheet.write(row, 1, value)
        row += 1

    workbook.save(output_file)


@click.command()
@click.option('-t', '--tripinfo', default="tripinfo.output.xml", help='Tripinfo xml file.')
@click.option('-d', '--dispatchinfo', help='Dispatchinfo xml file.')
@click.option('-r', '--direct-routes', help='Route file with direct routes of the booked requests.')
@click.option('-o', '--output', default="output.xls", help='Output Excel file.')
@click.option('-v', '--vtype', default="drt", help='Vehicle type to consider.')
@click.option('--depart-earliest', default=-1, type=float,
              help='Earliest departure to consider.')
@click.option('--arrival-latest', default=-1, type=float,
              help='Latest arrival to consider.')
def main(tripinfo, dispatchinfo, direct_routes, output, vtype, depart_earliest, arrival_latest):
    """
    Command line script for postprocessing of SUMO output files.

    Parameters
    ----------
    tripinfo : str or path-like
        Tripinfo xml file
    dispatchinfo : str or path-like, optional
        Dispatchinfo xml file.
    direct_routes : str or path-like, optional
        Route file with direct routes of the booked requests.
    output : str
        Output xls file.
    vtype: str, optional
        Only tripinfos with this vehicle type are considered.
        The default is 'drt'.
    depart_earliest: float, optional
        Skip personinfo entry which depart earlier than this.
        The default is -1, which means no filtering.
    arrival_latest: float, optional
        Skip personinfo entry which arrive later than this.
        The default is -1, which means no filtering.

    Returns
    -------
    None.

    """
    # Process output files and write stats to csv file.
    tripinfo_dict = process_tripinfo(
        tripinfo, vtype, depart_earliest, arrival_latest)
    if dispatchinfo:
        dispatch_dict = process_dispatchinfo(dispatchinfo)
    else:
        dispatch_dict = None
    if direct_routes:
        direct_routes_dict = process_direct_routes(direct_routes)
    else:
        direct_routes_dict = None
    output_dict = calculate_stats(tripinfo_dict, dispatch_dict, direct_routes_dict)
    dict2xls(output, output_dict)


if __name__ == '__main__':

    main()
