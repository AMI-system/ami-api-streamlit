#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script run an streamlit application for uploading files to an S3 bucket using presigned URLs.
It guides the user through selecting the deployment and data type and then uploads the specified files.
"""

from time import perf_counter
import asyncio
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import aiohttp
from aiohttp import BasicAuth
import nest_asyncio

nest_asyncio.apply()


# Function to fetch deployments from the URL with authentication
def get_deployments(user, pwd):
    """
    Fetches deployments from the specified URL using the provided username and password for authentication.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        list: A list of deployments if the request is successful, otherwise an empty list.
    """
    try:
        url = "https://connect-apps.ceh.ac.uk/ami-data-upload/get-deployments/"
        response = requests.get(url, auth=HTTPBasicAuth(user, pwd), timeout=600)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error: {err}")
        if response.status_code == 401:
            st.error("Wrong username or password. Try again!")
    except Exception as err:
        st.error(f"An error occurred: {err}")
    return []


async def get_presigned_url(user, pwd, name, bucket, dep_id, data_type, file_name):
    """
    Fetches a presigned URL for uploading a file using the provided details.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        name (str): The name associated with the upload.
        bucket (str): The S3 bucket name.
        dep_id (str): The deployment ID.
        data_type (str): The type of data being uploaded.
        file_name (str): The name of the file to be uploaded.

    Returns:
        dict: The JSON response containing the presigned URL if the request is successful.
    """
    url = "https://connect-apps.ceh.ac.uk/ami-data-upload/generate-presigned-url/"
    auth = BasicAuth(user, pwd)

    data = aiohttp.FormData()
    data.add_field("name", name)
    data.add_field("country", bucket)
    data.add_field("deployment", dep_id)
    data.add_field("data_type", data_type)
    data.add_field("filename", file_name)

    async with aiohttp.ClientSession(
        auth=auth, timeout=aiohttp.ClientTimeout(total=600)
    ) as session:
        async with session.post(url, data=data) as response:
            response.raise_for_status()
            return await response.json()


async def upload_file_to_s3(presigned_url, file_content, file_type):
    """
    Uploads a file to S3 using a presigned URL.

    Args:
        presigned_url (str): The presigned URL for uploading the file.
        file_content (bytes): The content of the file to be uploaded.
        file_type (str): The MIME type of the file.

    Returns:
        None
    """
    headers = {"Content-Type": file_type}
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=600)
    ) as session:
        async with session.put(
            presigned_url, data=file_content, headers=headers
        ) as response:
            response.raise_for_status()


async def upload_files_in_batches(
    user, pwd, name, bucket, dep_id, data_type, files, batch_size=50
):
    """
    Uploads files in batches to S3.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        name (str): The name associated with the upload.
        bucket (str): The S3 bucket name.
        dep_id (str): The deployment ID.
        data_type (str): The type of data being uploaded.
        files (list): A list of tuples containing file name, file content, and file type.
        batch_size (int, optional): The number of files to upload in each batch. Defaults to 50.

    Returns:
        None
    """
    for i in range(0, len(files), batch_size):
        end = i + batch_size
        batch = files[i:end]
        await upload_files(user, pwd, name, bucket, dep_id, data_type, batch)


async def upload_files(user, pwd, name, bucket, dep_id, data_type, files):
    """
    Uploads multiple files to S3 by first obtaining presigned URLs and then uploading the files.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        name (str): The name associated with the upload.
        bucket (str): The S3 bucket name.
        dep_id (str): The deployment ID.
        data_type (str): The type of data being uploaded.
        files (list): A list of tuples containing file name, file content, and file type.

    Returns:
        None
    """
    tasks = []
    for file_name, file_content, file_type in files:
        try:
            presigned_url = await get_presigned_url(
                user, pwd, name, bucket, dep_id, data_type, file_name
            )
            task = upload_file_to_s3(presigned_url, file_content, file_type)
            tasks.append(task)
        except Exception as e:
            st.error(f"Error getting presigned URL for {file_name}: {e}")
    await asyncio.gather(*tasks)


def main(user, pwd, deployments):
    """
    The main function to handle the user interface and interaction in the Streamlit app.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        deployments (list): A list of deployments fetched from the server.

    Returns:
        None
    """
    if not deployments:
        st.error(
            "No deployments found. Please check your credentials or network connection."
        )
        return

    full_name = st.text_input("Your Full Name:", key="full_name")

    valid_country_names = list(
        {d["country"] for d in deployments if d["status"] == "active"}
    )
    country = st.selectbox(
        "Country:", ["Select Country"] + valid_country_names, key="country"
    )

    if "deployment_names" not in st.session_state:
        st.session_state.deployment_names = []

    if country != "Select Country":
        st.session_state.deployment_names = [
            f"{d['location_name']} - {d['camera_id']}"
            for d in deployments
            if d["country"] == country and d["status"] == "active"
        ]

    deployment = st.selectbox(
        "Deployment:",
        ["Select Deployment"] + st.session_state.deployment_names,
        key="deployment",
    )

    data_type = st.selectbox(
        "Data type:",
        [
            "Select Data Type",
            "snapshot_images",
            "audible_recordings",
            "ultrasound_recordings",
        ],
        key="data_type",
    )

    with st.form("my_form", clear_on_submit=True, border=False):
        uploaded_files = st.file_uploader(
            "Select Files:",
            accept_multiple_files=True,
            type=["jpg", "jpeg", "png", "mp3", "wav"],
            help="Maximum 1000 files can be selected.",
        )

        max_num_files = 1000
        if uploaded_files and len(uploaded_files) > max_num_files:
            st.warning(
                f"""You have exceeded the maximum limit of {max_num_files} files.
                Only the first {max_num_files} will be pushed to the server."""
            )
            uploaded_files = uploaded_files[:max_num_files]

        submitted = st.form_submit_button("Upload")
        if submitted:
            handle_upload(
                user,
                pwd,
                full_name,
                country,
                deployment,
                data_type,
                uploaded_files,
                deployments,
            )


def handle_upload(
    user,
    pwd,
    full_name,
    country,
    deployment,
    data_type,
    uploaded_files,
    deployments,
):
    """
    Handles the file upload process by validating inputs and initiating the upload.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        full_name (str): The full name of the user.
        country (str): The selected country.
        deployment (str): The selected deployment.
        data_type (str): The type of data being uploaded.
        uploaded_files (list): A list of uploaded files.
        deployments (list): A list of deployments fetched from the server.

    Returns:
        None
    """
    if not full_name:
        st.warning("Please enter your full name.")
    elif country == "Select Country":
        st.warning("Please select a country.")
    elif deployment == "Select Deployment":
        st.warning("Please select a deployment.")
    elif data_type == "Select Data Type":
        st.warning("Please select a data type.")
    elif not uploaded_files:
        st.warning("Please upload at least one file.")
    else:
        start_time = perf_counter()

        try:
            files = [(file.name, file.read(), file.type) for file in uploaded_files]

            s3_bucket_name = [
                d["country_code"]
                for d in deployments
                if d["country"] == country and d["status"] == "active"
            ][0].lower()
            location_name, camera_id = deployment.split(" - ")
            dep_id = [
                d["deployment_id"]
                for d in deployments
                if d["country"] == country
                and d["location_name"] == location_name
                and d["camera_id"] == camera_id
                and d["status"] == "active"
            ][0]

            with st.spinner("Uploading..."):
                asyncio.run(
                    upload_files_in_batches(
                        user,
                        pwd,
                        full_name,
                        s3_bucket_name,
                        dep_id,
                        data_type,
                        files,
                    )
                )

            st.success("Files uploaded successfully!")
        except Exception as e:
            st.error(f"Failed to upload files. Error: {e}")

        end_time = perf_counter()
        print(f"Upload files took: {end_time - start_time} seconds.")


if __name__ == "__main__":
    st.title("Upload Files")

    username = st.text_input("Username:", key="username")
    password = st.text_input("Password:", type="password", key="password")

    if st.button("Login"):
        if username and password:
            st.session_state.deployments = get_deployments(username, password)
        else:
            st.warning("Please enter your username and password")

    if "deployments" in st.session_state:
        main(username, password, st.session_state.deployments)
