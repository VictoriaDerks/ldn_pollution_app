"""
Testing OpenAir API requests.
Obtaining site data.
"""
import json
import os
from io import StringIO
import pandas as pd
import requests
import urllib


def get_info(uri: str, file_format: str = "", save: bool = False, verbose: bool = False):
    """
    Make a GET request to the Open Air API.

    :param verbose:
    :param uri:
    :param file_format: default = "", produces .xml file upon save
    :param save:
    :return:
    """
    basic_url = "https://api.erg.ic.ac.uk/AirQuality/"

    if file_format.lower() == "json":
        uri = uri + "/" + file_format.title()
    elif file_format.lower() == "csv":
        uri = uri + "/" + file_format.lower()

    full_url = urllib.parse.urljoin(basic_url, uri, allow_fragments=True)

    response = requests.get(full_url)
    if verbose:
        print(response.text)

    if response.status_code >= 400:  # request failed
        return False

    if not file_format:
        file_format = "xml"

    if save:
        # if the json/xml looks bad, you can use this to format it: https://jsonformatter.curiousconcept.com/#
        with open(f"traffic.{file_format.lower()}", "w", encoding="utf-8") as f:
            f.write(response.text)

    return response.text


def get_site_data(uri: str, startdate: str, enddate: str, save: bool = False):
    """
    Get the data by making API requests.

    :param uri:
    :param startdate:
    :param enddate:
    :param save:
    :return:
    """
    with open("heatmap_and_dataloading/sites.json", "r") as f:
        sites_info = json.load(f)

    site_info = {}

    for site in sites_info["Sites"]["Site"]:
        site_code = site["@SiteCode"]
        # site_code = "CD9"
        current_uri = uri.replace("{SiteCode}", site_code)
        current_uri = current_uri.replace("{StartDate}", startdate)
        current_uri = current_uri.replace("{EndDate}", enddate)

        data = get_info(uri=current_uri, file_format="json", save=False)

        if not data:  # incorrect response from server
            print("Invalid response.")
            continue

        site_df = pd.read_csv(StringIO(data), index_col=["MeasurementDateGMT"], parse_dates=["MeasurementDateGMT"])

        if ',' in site["@SiteName"]:
            site_name = site["@SiteName"].split(",")[0]
        else:
            site_name = site["@SiteName"]

        site_df.columns = site_df.columns.str.replace(f'{site_name}: ', '')

        site_info[site_code] = site_df
        print(f"Loaded: {site['@SiteName']}")

        if save:
            site_df.to_csv(f"data/{site_code}_data.json")
            print(f"Created file for: {site['@SiteName']} data.")

    return site_info


def load_from_file(data_path="./data"):
    """
    Initialise dataframes from files. Faster than API calls in get_site_data().
    :param data_path: location of data folder
    :return: 
    """
    site_info = {}
    files = os.listdir(data_path)
    codes = [x.split("_")[0] for x in files]

    for code in codes:
        df = pd.read_csv(f"{data_path}/{code}_data.csv", encoding="utf-8",
                         index_col=["MeasurementDateGMT"],
                         parse_dates=["MeasurementDateGMT"])
        # df.fillna(-1, inplace=True)
        site_info[code] = df

    return site_info


if __name__ == '__main__':
    # monitoring groups request
    uri_groups = "Information/Groups"

    # request for info about sites in the London group
    uri_sites = "Information/MonitoringSites/GroupName=London"

    # which site monitors what for London sites
    uri_species = "Information/MonitoringSiteSpecies/GroupName=London"

    # data from [site] from [start] to [end] in json format
    uri_data_json = "Data/Site/SiteCode={SiteCode}/StartDate={StartDate}/EndDate={EndDate}"

    # data from [site] from [start] to [end] in csv format
    uri_data_csv = "Data/Site/Wide/SiteCode={SiteCode}/StartDate={StartDate}/EndDate={EndDate}"

    uri_traffic = "/Data/Traffic/Site/SiteCode=KC3/StartDate=08-04-2019/EndDate=08-04-2020"

    # information about species types and their codes
    uri = "Information/Species"

    # get_site_data(uri=uri_data_json, startdate="2016-04-08", enddate="2021-04-08", save=True)

    # get_info(uri=uri, file_format="Json", save=True)

    load_from_file(data_path="data")

