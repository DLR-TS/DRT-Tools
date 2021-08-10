# -*- coding: utf-8 -*-
""" Command line interface to process SUMO output files.

Created on Tue Dec 08 11:04:00 2020

@author: ritz_ph
"""

import click
import numpy as np
import pathlib

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

import xlwt


def get_root(path):
    path = pathlib.Path(path)
    try:
        tree = etree.parse(path.as_posix())
    except:
        raise Exception("Error loading file {}.".format(path.as_posix()))
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


def process_tripinfo(tripinfo_path, vtype='drt'):
    """
    Process data of tripinfo output file.

    Parameters
    ----------
    tripinfo_path : str
        Path of tripinfo file.
    vtype: str, optional
        Only tripinfos with this vehicle type are considered.
        The default is 'drt'.

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
    # filter for vehicle type
    list_tripinfo = root_tripinfo.findall(
        "tripinfo[@vType='{0}']".format(vtype))

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
    # number of raw personinfo entries
    n_personinfo_raw = len(list_personinfo)

    n_filtered = 0  # filtered personinfo (faulty entries)
    n_walking_only = 0  # personinfo with walk but without ride

    for personinfo in list_personinfo:
        completed = True

        list_ride = personinfo.findall("ride")
        list_walk = personinfo.findall("walk")

        if list_walk and not list_ride:
            n_walking_only += 1

        for ride in list_ride:
            # skip personinfo with depart < 0
            if float(ride.get("depart")) < 0:
                completed = False
            # skip personinfo with arrival < 0
            if float(ride.get("arrival")) < 0:
                completed = False
            # skip personinfo with routeLength < 0
            if float(ride.get("routeLength")) < 0:
                completed = False
            # skip personinfo with vehicle "NULL"
            if ride.get("vehicle") == "NULL":
                completed = False
            if not completed:
                n_filtered += 1
                break
            timeloss_ride.append(ride.get("timeLoss"))
            duration_ride.append(ride.get("duration"))
            waiting_ride.append(ride.get("waitingTime"))
            length_ride.append(ride.get("routeLength"))
        if not completed:
            # skip this personinfo entry
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


def calculate_stats(tripinfo_dict, dispatch_dict):

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
            "passengers_per_time_driving"]
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
@click.option('-o', '--output', default="output.xls", help='Output Excel file.')
@click.option('-d', '--dispatchinfo', help='Dispatchinfo xml file.')
@click.option('-v', '--vtype', default="drt", help='Vehicle type to consider.')
def main(tripinfo, dispatchinfo, output, vtype):
    """
    Command line function to run post-processing and write output file.

    Parameters
    ----------
    tripinfo : str or path-like
        Tripinfo xml file
    dispatchinfo : str or path-like, optional
        Dispatchinfo xml file.
    output : str
        Output xls file.

    Returns
    -------
    None.

    """
    # Process output files and write stats to csv file.
    tripinfo_dict = process_tripinfo(tripinfo, vtype)
    if dispatchinfo:
        dispatch_dict = process_dispatchinfo(dispatchinfo)
    else:
        dispatch_dict = None
    output_dict = calculate_stats(tripinfo_dict, dispatch_dict)
    dict2xls(output, output_dict)


if __name__ == '__main__':

    main()
