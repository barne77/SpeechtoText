import logging

import azure.functions as func
import io
import os
from azure.storage.blob import BlobServiceClient
from pydub import AudioSegment


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        connection_string = ""
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        container_name = 'stereofiles'
        container_name_output = 'monofiles'

        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(name)
        container_client_output = blob_service_client.get_container_client(container_name_output)
        blob_client_output = container_client_output.get_blob_client(name)

        blob_data = blob_client.download_blob().readall()
        blob_data = bytearray(blob_data)
        file_obj = io.BytesIO(blob_data)

        #sound = AudioSegment.from_file(file_obj, sample_width=2, frame_rate=8000, channels=1, format='wav')
        sound = AudioSegment.from_file(file_obj,channels=1, format='wav')
        blob_client_output.upload_blob(sound.export(format="wav"), overwrite=True)

        return func.HttpResponse(f"Converted audio file: {blob_client} -> {blob_client_output}",status_code=200)
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )

