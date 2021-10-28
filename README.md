# ldn_pollution_app
Creating interactive maps for visualing air pollution in London over time

## What is this?
This code creates the London pollution visualisations over time that can be found at https://ldn-airpollution-app.herokuapp.com/.

All data comes from the London Air Quality Network API, and London Datastore for geographic info. 

## Which file does what?
* `app.py` to run the website locally
* `mapmaking.py` to create the pollution maps
* `dataloading.py` for requesting data from the London Air Quality Network API
* `timestamped_geo_json.py` is a slightly modified version of the TimestampedGeoJson folium plugin (https://python-visualization.github.io/folium/plugins.html), 
that allows for frame rate to be sped up.
