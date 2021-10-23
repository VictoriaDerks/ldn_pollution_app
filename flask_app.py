"""
Running a local server to display the maps.

To run: just run this file and follow the link it provides.

Usually: http://localhost:5000.
"""

import os

from flask import Flask, render_template

from mapmaking import create_layered_map

app = Flask(__name__, template_folder=os.path.join(os.getcwd()))


@app.route('/NO2_map')
def NO2_map():
    return map("NO2")


@app.route('/PM10_map')
def PM10_map():
    return map("PM10")


@app.route('/PM25_map')
def PM25_map():
    return map("PM25")


def map(species_code):
    if os.path.isfile(f"ULEZ_map_{species_code}.html"):
        return render_template(f"ULEZ_map_{species_code}.html")
    else:  # create new map if map doesn't already exist
        folium_map = create_layered_map(species_code, save=False)

    return folium_map._repr_html_()


@app.route('/')
def index():
    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=False)
