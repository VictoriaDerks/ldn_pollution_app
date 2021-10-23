"""
For generating various maps of pollutant level per monitoring site in London.
"""

import json
import os
import itertools

import matplotlib
import numpy as np
import pandas as pd
from folium.plugins import HeatMapWithTime
from matplotlib import pyplot as plt

from dataloading import load_from_file
from timestamped_geo_json import TimestampedGeoJson
import folium


def get_lat_long_dict() -> dict:
    """
    Get longitude, latitude and site name for all sites.
    :return: dictionary where key = site code & values are a lat, long list and a site name
    """
    with open("./helper_files/monitoring.json", "r") as f:
        info_json = json.load(f)

    lat_long_dict = {}

    for site in info_json["Sites"]["Site"]:
        if not (site["@Longitude"] and site["@Latitude"]):  # exclude sites without coords
            continue

        lat_long_dict[site["@SiteCode"]] = ([float(site["@Latitude"]), float(site["@Longitude"])], site["@SiteName"])

    return lat_long_dict


def create_heatmap(data_dict: dict, species_code: str):
    """
    Creates heatmap of data over time for all sites & times specified in the data dictionary.
    Type of pollutant to plot can be detemined with the species code
    :param data_dict: dictionary where key = site code, and value = dataframe with site data
    :param species_code: possible species: {'NO2', 'O3', 'PM10', 'SO2', 'PM25', 'CO'}
    :return:
    """

    # map species code to their column name in the file
    species_col = get_col_name(species_code)

    lat_long_dict = get_lat_long_dict()

    possible_sites = get_sites_by_pollutant(species_code)

    available_sites = set([x.split("_")[0] for x in os.listdir("data")])

    # group dataframes for the possible sites by week
    for site_code in possible_sites:
        if site_code in available_sites:
            data_dict[site_code] = data_dict[site_code].groupby(data_dict[site_code].index.to_period("W")).mean()

    # get upper and lower values, so outliers are excluded
    all_val = [list(data_dict[x][species_col]) for x in possible_sites if x in available_sites and
               species_col in data_dict[x].columns]  # all species values for all sites in one list
    all_val = list(itertools.chain.from_iterable(all_val))  # flatten
    all_val = [x for x in all_val if not np.isnan(x)]  # remove nan

    quantile_upper = np.quantile(all_val, 0.75)
    quantile_lower = np.quantile(all_val, 0.25)
    iqr = quantile_upper - quantile_lower
    # max possible values is 3rd quantile + 1.5 * inter-quartile range. Scale can be adjusted if necessary
    max_val = quantile_upper + iqr * 1.5
    min_val = quantile_lower - iqr * 1.5

    # putting data in correct format for HeatmapWithTime
    first_df = data_dict[possible_sites[0]]
    timeseries_list = list(first_df.index)
    data_list = []
    for i, time in enumerate(timeseries_list):
        shortlist = []
        for site_code in possible_sites:

            # exclude irrelevant sites or improper column names
            if site_code not in available_sites or species_col not in data_dict[site_code].columns:
                continue

            current_df = data_dict[site_code]
            current_species_data = current_df.loc[time, species_col]

            # exclude nans and outliers
            if np.isnan(current_species_data) or current_species_data > max_val or current_species_data < min_val:
                continue

            (lat, long), _ = lat_long_dict[site_code]
            merged_lists = [lat, long, current_species_data]
            # merged_lists = tuple([round(lat, 3), round(long, 3)])
            shortlist.append(merged_lists)
        data_list.append(shortlist)
        # progress update
        if i % 100 == 0:
            print(f"processed {i}/{timeseries_list.__len__()} dates")

    # normalising values
    for timepoint in data_list:
        for location in timepoint:
            location[2] = (location[2] - min_val) / (max_val - min_val)

    ldn_coords = [51.509865, -0.118092]

    folium_hmap = folium.Map(location=ldn_coords, zoom_start=11,
                             tiles="CartoDB dark_matter"
                             )

    hmap_layer = HeatMapWithTime(data_list,
                                 index=list(data_dict[possible_sites[0]].index.astype(str)),
                                 use_local_extrema=False, name="Heat Map",
                                 min_speed=5,
                                 max_speed=50,
                                 speed_step=1,
                                 radius=20, display_index=True, overlay=True, control=True)

    folium_hmap.add_child(hmap_layer)
    # folium_hmap.add_child(folium.FeatureGroup(name='Heat Map').add_child(hmap_layer))
    folium.LayerControl().add_to(folium_hmap)

    folium_hmap.save("heatmap_and_dataloading/hmap_london_positron.html")

def get_sites_by_pollutant(species_code: str) -> list:
    """
    Get sites that track the relevant pollutant and their coordinates

    :param species_code: options are NO2, O3, PM10, SO2, PM25, CO
    :return:
    """
    with open("./helper_files/monitoring.json", "r") as f:
        monitoring_info = json.load(f)

    possible_sites = []
    for site in monitoring_info["Sites"]["Site"]:
        if isinstance(site["Species"], list):  # site tracks a list of different pollutants
            site_species = [x["@SpeciesCode"] for x in site["Species"]]
            if species_code in site_species:
                possible_sites.append(site["@SiteCode"])
        else:  # site only tracks a single pollutant
            if species_code == site["Species"]["@SpeciesCode"]:
                possible_sites.append(site["@SiteCode"])
    return possible_sites


def get_col_name(species_code: str) -> str:
    """
    From pollutant code to its column name in a csv file.
    :param species_code: options are NO2, O3, PM10, SO2, PM25, CO
    :return:
    """
    species_to_col = {"NO2": "Nitrogen Dioxide (ug/m3)",
                      "O3": 'Ozone (ug/m3)',
                      'PM10': 'PM10 Particulate (ug/m3)',
                      'SO2': "Sulphur Dioxide (ug/m3)",
                      'PM25': 'PM2.5 Particulate (ug/m3)',
                      'CO': 'Carbon Monoxide (mg/m3)'}

    return species_to_col[species_code]


# TODO gradient
def site_locations(species_code: str) -> folium.FeatureGroup:
    """
    Marks all relevant sites on the map which track the required pollutant and have data available.
    :param species_code:
    :return:
    """
    with open("helper_files/sites.json", "r") as f:
        site_info = json.load(f)

    sites_dict = load_from_file()

    species_col_name = get_col_name(species_code)

    feature_group = folium.FeatureGroup('Sites')

    relevant_sites = get_sites_by_pollutant(species_code)

    available_sites = set([x.split("_")[0] for x in os.listdir("./data")])

    useful_sites = set(relevant_sites).intersection(available_sites)

    for site in site_info["Sites"]["Site"]:
        if not (site["@Longitude"] and site["@Latitude"]):  # exclude sites without coords
            continue

        if site["@SiteCode"] not in useful_sites:  # skip sites without pollutant info
            continue

        site_df = sites_dict[site["@SiteCode"]]
        if species_col_name not in site_df.columns:  # skip sites that don't have the required column
            continue

        if np.all(site_df[species_col_name].isna()):  # skip sites that don't have data in the time period
            continue

        site_coord = tuple([float(site["@Latitude"]), float(site["@Longitude"])])
        popup_text = site["@SiteName"]
        colour = "#9c9a95"  # light grey

        folium.CircleMarker(
            location=site_coord,
            radius=10,
            popup=popup_text,
            color=colour,
            fill=True,
            stroke=False,
            weight=1,
            fill_color=colour,
            fill_opacity=0.4
        ).add_to(feature_group)

    return feature_group


def ulez_line() -> folium.FeatureGroup:
    """
    Shape on the map that shows ULEZ border and area
    :return:
    """

    ulez_df = pd.read_csv("./helper_files/ULEZ_coordinates.csv")

    lat = list(ulez_df["lat"])
    long = list(ulez_df["long"])

    feature_group = folium.FeatureGroup('ULEZ area')

    coords = list(zip(long, lat))

    # polygon as JSON
    poly_feature = {"type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords]
                    }
                    }

    gjson = folium.GeoJson(poly_feature,
                           style_function=lambda x: {'fillColor': 'blue', 'fillOpacity': 0},  # normal styling
                           highlight_function=lambda x: {'fillColor': '#3388ff', 'fillOpacity': 0.1})  # style on hover

    folium.Popup("<b>ULEZ</b> border").add_to(gjson)  # text when area is clicked

    gjson.add_to(feature_group)

    return feature_group


def extended_ulez_line():
    extended_ulez_df = pd.read_csv("./helper_files/ULEZ_extended_coordinates.csv")
    ulez_df = pd.read_csv("./helper_files/ULEZ_coordinates.csv")  # hole in polygon

    lat = list(extended_ulez_df["lat"])
    long = list(extended_ulez_df["long"])
    coords = list(zip(long, lat))

    lat_hole = list(ulez_df["lat"])
    long_hole = list(ulez_df["long"])
    coords_hole = list(zip(long_hole, lat_hole))

    feature_group = folium.FeatureGroup('ULEZ extended area')

    # polygon as JSON
    poly_feature = {"type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords,
                                        coords_hole]
                                }
                    }

    gjson = folium.GeoJson(poly_feature,
                           style_function=lambda x: {'fillColor': 'green', 'fillOpacity': 0, 'color': '#1DA237'},  # normal styling
                           highlight_function=lambda x: {'fillColor': '#1DA237', 'fillOpacity': 0.1})  # style on hover

    folium.Popup("<b>Extended ULEZ</b> border").add_to(gjson)  # text when area is clicked

    gjson.add_to(feature_group)

    return feature_group


def pollution_map(species_code: str, create_map: bool = False) -> TimestampedGeoJson:
    """
    Creates an interactive layer with monitoring sites and pollution levels indicated by site colour.
    :param species_code:
    :param create_map: determines whether to save the layer as a map in itself
    :return:
    """
    sites_dict = load_from_file()  # key = site code, value = pd.Dataframe with monitoring info

    species_col = get_col_name(species_code)  # column name in csv for the species code

    lat_long_dict = get_lat_long_dict()  # key = site code, value = lat, long, site name

    relevant_sites = get_sites_by_pollutant(species_code)  # list of sites that track the selected pollutant

    available_sites = set([x.split("_")[0] for x in os.listdir("./data")])

    useful_sites = set(relevant_sites).intersection(available_sites)

    # group dataframes for the possible sites by week
    for site_code in useful_sites:
        sites_dict[site_code] = sites_dict[site_code].groupby(sites_dict[site_code].index.to_period("W")).mean()

    # creating GEOJSON feature objects
    features = []

    colourmap = plt.get_cmap('plasma')  # used when colouring sites based on pollutant level

    # get upper and lower values for all data, so outliers are excluded
    all_val = [list(sites_dict[x][species_col]) for x in useful_sites if
               species_col in sites_dict[x].columns]  # all species values for all sites in one list
    all_val = list(itertools.chain.from_iterable(all_val))  # flatten
    all_val = [x for x in all_val if not np.isnan(x)]  # remove nan

    quantile_upper = np.quantile(all_val, 0.75)
    quantile_lower = np.quantile(all_val, 0.25)
    iqr = quantile_upper - quantile_lower
    # max possible values is 3rd quantile + 1.5 * inter-quartile range. Scale can be adjusted if necessary
    max_val = quantile_upper + iqr * 1.5
    min_val = quantile_lower - iqr * 1.5

    for site_key in list(useful_sites):
        (lat, long), site_name = lat_long_dict[site_key]

        if species_col not in sites_dict[site_key].columns:  # pollutant column not present, skip
            continue

        df = sites_dict[site_key]
        for _, row in df.iterrows():
            species_val = row.loc[species_col]

            if np.isnan(species_val):  # exclude nans
                continue

            # exclude outliers
            if species_val > max_val or species_val < min_val:
                continue

            # normalise registered value and picking corresponding colour
            colour_val = (species_val - min_val) / (max_val - min_val)
            colour = matplotlib.colors.to_hex(colourmap(colour_val), keep_alpha=False)

            date_str = row.name.start_time.__str__()[:10]  # exclude h:m:s info
            text = f"{site_name}<br />{round(species_val, 2)} {species_col}"  # shows on site click

            # make data a json feature
            feature = create_feature_json(lat=lat, long=long, date=date_str, color=colour,
                                          popuptext=text)
            features.append(feature)

    # map making
    timejson = TimestampedGeoJson(
        {'type': 'FeatureCollection',
         'features': features},
        period='P1W',
        add_last_point=True,
        auto_play=False,
        loop=False,
        min_speed=5,
        max_speed=50,
        loop_button=True,
        date_options='YYYY-MM-DD',
        time_slider_drag_update=True,
        speed_step=1,
        name=f"Time Map for {species_code}",
        overlay=True,
        control=True
    )

    if create_map:
        m = folium.Map(location=[51.509865, -0.118092], tiles="Stamen Toner", zoom_start=11)

        timejson.add_to(m)

        folium.LayerControl().add_to(m)

        m.save("timemap_test.html")

    return timejson

def create_layered_map(species_code: str, save: bool = True) -> folium.Map:
    """
    Creates the full folium map with layers:
    - sites layer: all relevant sites in a grey colour
    - time layer: shows pollution over time per site using colour
    - ulez area layer: displays the ULEZ on the map
    :param species_code:
    :param save: whether to save the generated map
    :return: folium.Map object with all layers
    """
    m = folium.Map(location=[51.509865, -0.118092], tiles="Stamen Toner", zoom_start=11)
    # extended ulez border
    extended_ulez_layer = extended_ulez_line()
    extended_ulez_layer.add_to(m)

    # layer with ulez outline
    ulez_layer = ulez_line()
    ulez_layer.add_to(m)

    # grey bottom layer of all relevant sites
    # sites_layer = site_locations(species_code)
    # sites_layer.add_to(m)

    # layer with pollution over time
    time_layer = pollution_map(species_code=species_code)
    time_layer.add_to(m)

    folium.LayerControl().add_to(m)

    if save:
        m.save(f"ULEZ_map_{species_code}.html")

    return m


def create_feature_json(lat: float, long: float, date: str, color: str, popuptext: str) -> dict:
    """
    For creating json features in the GEOJSON format.
    :param lat:
    :param long:
    :param date:
    :param color: hexadecimal string
    :param popuptext: appears when clicking on the monitoring site
    :return: dictionary object that represents a json structure
    """
    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [long, lat]
        },
        'properties': {
            'time': date,
            # 'style': {'color': color},
            'icon': 'circle',
            'popup': popuptext,
            'iconstyle': {
                'fillColor': color,
                'fillOpacity': 0.8,
                'weight': 1,
                'color': color,
                'stroke': 'false',
                'fill': 'true',
                'radius': 10
            }
        }
    }


if __name__ == '__main__':
    # create_heatmap(site_dict, "O3")

    create_layered_map("PM25", save=False)
