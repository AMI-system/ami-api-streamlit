import streamlit as st
import json
from time import perf_counter
import requests
from requests.auth import HTTPBasicAuth
import asyncio
import aiohttp
from aiohttp import BasicAuth
import nest_asyncio

nest_asyncio.apply()

# Function to fetch deployments from the URL with authentication
def get_deployments(username, password):
    url = "https://connect-apps.ceh.ac.uk/ami-data-upload/get-deployments/"
    response = requests.get(url, auth=HTTPBasicAuth(username, password))
    if response.status_code == 200:
        deployments = response.json()
        return deployments
    else:
        return []

# Async function to upload files
async def upload_file(username, password, name, bucket, dep_id, data_type, files):
    url = 'https://connect-apps.ceh.ac.uk/ami-data-upload/upload/'
    auth = BasicAuth(username, password)

    data = aiohttp.FormData()
    data.add_field('name', name)
    data.add_field('country', bucket)
    data.add_field('deployment', dep_id)
    data.add_field('data_type', data_type)

    for file in files:
        data.add_field('files', file.read(), filename=file.name, content_type=file.type)

    async with aiohttp.ClientSession(auth=auth) as session:
        async with session.post(url, data=data) as response:
            return response


# Input fields for username and password (for demo purposes, this should be securely handled)
username = st.text_input('Username:', key='username')
password = st.text_input('Password:', type='password', key='password')

if username and password:
    # Fetch deployments
    deployments = get_deployments(username, password)
else:
    deployments = []

# Title of the app
st.title('Upload Files')


# Full name input
full_name = st.text_input('Your Full Name:', key='full_name')

# Country selection
valid_country_names = list(set([d['country'] for d in deployments if d['status'] == 'active']))
country = st.selectbox('Country:', ['Select Country'] + valid_country_names, key='country')

# Fetch deployments for the selected country
if 'deployment_names' not in st.session_state:
    st.session_state.deployment_names = []

if country != 'Select Country':
    st.session_state.deployment_names = [f"{d['location_name']} - {d['camera_id']}" for d in deployments
                                         if d['country'] == country and d['status'] == 'active']

# Deployment selection
deployment = st.selectbox('Deployment:', ['Select Deployment'] + st.session_state.deployment_names, key='deployment')

# Data type selection
data_type = st.selectbox('Data type:', ['Select Data Type', "snapshot_images",
                                        "audible_recordings", "ultrasound_recordings"], key='data_type')

if "file_uploader_key" not in st.session_state:
    st.session_state["file_uploader_key"] = 0

if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = []

# File uploader with a check for the number of uploaded files
uploaded_files = st.file_uploader(
    'Select Files:',
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'mp3', 'wav', 'ogg'],
    help='Maximum 1000 files can be selected.',
    key=st.session_state["file_uploader_key"]
)

if uploaded_files:
    st.session_state["uploaded_files"] = uploaded_files

if uploaded_files is not None:
    if len(uploaded_files) > 1000:
        st.warning('You have exceeded the maximum limit of 1000 files. Please select fewer files.')
        uploaded_files = []

if st.button("Clear uploaded files"):
    st.session_state["file_uploader_key"] += 1
    st.rerun()

# Upload button
if st.button('Upload'):
    if not full_name:
        st.warning('Please enter your full name.')
    elif country == 'Select Country':
        st.warning('Please select a country.')
    elif deployment == 'Select Deployment':
        st.warning('Please select a deployment.')
    elif data_type == 'Select Data Type':
        st.warning('Please select a data type.')
    elif not uploaded_files:
        st.warning('Please upload at least one file.')
    else:
        start_time = perf_counter()
        
        # Prepare files for upload
        files = [file for file in uploaded_files]

        s3_bucket_name = [d['country_code'] for d in deployments
                          if d['country'] == country and d['status'] == 'active'][0].lower()
        location_name, camera_id = deployment.split(' - ')
        dep_id = [d['deployment_id'] for d in deployments
                  if d['country'] == country and
                  d['location_name'] == location_name and
                  d['camera_id'] == camera_id and
                  d['status'] == 'active'][0]
        
        response = asyncio.run(upload_file(username, password, full_name,
                                           s3_bucket_name, dep_id,
                                           data_type, files))

        if response.status == 200:
            st.success("Files uploaded successfully!")
        else:
            st.error(f"Failed to upload files. Status code: {response.status}")

        end_time = perf_counter()
        print(f"Upload files took: {end_time - start_time} seconds.")

# To run this app, save it as `app.py` and run the following command in your terminal:
# streamlit run app.py
