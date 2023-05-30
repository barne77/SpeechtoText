import logging
import azure.functions as func
from datetime import datetime
from functools import reduce
from http import HTTPStatus
from itertools import chain
from json import dumps, loads
from os import linesep
from pathlib import Path
from time import sleep
from typing import Dict, List, Tuple
from pydub import AudioSegment
import uuid
from . import helper
from . import rest_helper
from . import user_config_helper
import pymysql
import os
import json
import typing
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient, HealthcareEntityRelation

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
        # This should not change unless you switch to a new version of the Speech REST API.
        SPEECH_TRANSCRIPTION_PATH = "/speechtotext/v3.0/transcriptions"

        # These should not change unless you switch to a new version of the Cognitive Language REST API.
        SENTIMENT_ANALYSIS_PATH = "/language/:analyze-text";
        SENTIMENT_ANALYSIS_QUERY = "?api-version=2022-05-01";
        CONVERSATION_ANALYSIS_PATH = "/language/analyze-conversations/jobs";
        CONVERSATION_ANALYSIS_QUERY = "?api-version=2022-10-01-preview";
        CONVERSATION_SUMMARY_MODEL_VERSION = "2022-05-15-preview";
        MYSQL_SERVER_NAME = "";
        MYSQL_SERVER_DB = "";
        MYSQL_SERVER_UNAME = "";
        MYSQL_SERVER_PASS = "";
        CONN_ENDPOINT = "";
        CONN_KEY = "";

        # How long to wait while polling batch transcription and conversation analysis status.
        WAIT_SECONDS = 10

        class TranscriptionPhrase(object) :
            def __init__(self, id : int, text : str, itn : str, lexical : str, speaker_number : int, offset : str, offset_in_ticks : float) :
                self.id = id
                self.text = text
                self.itn = itn
                self.lexical = lexical
                self.speaker_number = speaker_number
                self.offset = offset
                self.offset_in_ticks = offset_in_ticks
        
        class SentimentAnalysisResult(object) :
            def __init__(self, speaker_number : int, offset_in_ticks : float, document : Dict) :
                self.speaker_number = speaker_number
                self.offset_in_ticks = offset_in_ticks
                self.document = document

        class ConversationAnalysisSummaryItem(object) :
            def __init__(self, aspect : str, summary : str) :
                self.aspect = aspect
                self.summary = summary

        class ConversationAnalysisPiiItem(object) :
            def __init__(self, category : str, text : str) :
                self.category = category
                self.text = text

        class ConversationAnalysisForSimpleOutput(object) :
            def __init__(self, summary : List[ConversationAnalysisSummaryItem], pii_analysis : List[List[ConversationAnalysisPiiItem]]) :
                self.summary = summary
                self.pii_analysis = pii_analysis

# This needs to be serialized to JSON, so we use a Dict instead of a class.
        def get_combined_redacted_content(channel : int) -> Dict :
            return {
                "channel" : channel,
                "display" : "",
                "itn" : "",
                "lexical" : ""
             }

        def create_transcription(user_config : helper.Read_Only_Dict) -> str :
            uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}"

    # Create Transcription API JSON request sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/CreateTranscription
    # Notes:
    # - locale and displayName are required.
    # - diarizationEnabled should only be used with mono audio input.
            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(name  + "\n")
            content = {
                #"contentUrls" : [user_config["input_audio_url"]],
                "contentUrls" : [name],
                "properties" : {
                    "diarizationEnabled" : not user_config["use_stereo_audio"],
                    "timeToLive" : "PT30M"
                },
                "locale" : user_config["locale"],
                "displayName" : f"call_center_{datetime.now()}",
            }

            response = rest_helper.send_post(uri=uri, content=content, key=user_config["speech_subscription_key"], expected_status_codes=[HTTPStatus.CREATED])
    
    # Create Transcription API JSON response sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/CreateTranscription
            transcription_uri = response["json"]["self"]
    # The transcription ID is at the end of the transcription URI.
            transcription_id = transcription_uri.split("/")[-1];
    # Verify the transcription ID is a valid GUID.
            try :
                uuid.UUID(transcription_id)
                return transcription_id
            except ValueError:
                raise Exception(f"Unable to parse response from Create Transcription API:{linesep}{response['text']}")

        def get_transcription_status(transcription_id : str, user_config : helper.Read_Only_Dict) -> bool :
            uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}"
            response = rest_helper.send_get(uri=uri, key=user_config["speech_subscription_key"], expected_status_codes=[HTTPStatus.OK])
                raise Exception(f"Unable to transcribe audio input. Response:{linesep}{response['text']}")
            else :
                return "succeeded" == response["json"]["status"].lower()

        def wait_for_transcription(transcription_id : str, user_config : helper.Read_Only_Dict) -> None :
            done = False
            while not done :
                print(f"Waiting {WAIT_SECONDS} seconds for transcription to complete.")
                #Write to output file
                with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Waiting {WAIT_SECONDS} seconds for transcription to complete."  + "\n")
                sleep(WAIT_SECONDS)
                done = get_transcription_status(transcription_id, user_config=user_config)

        def get_transcription_files(transcription_id : str, user_config : helper.Read_Only_Dict) -> Dict :
            uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}/files"
            response = rest_helper.send_get(uri=uri, key=user_config["speech_subscription_key"], expected_status_codes=[HTTPStatus.OK])
            return response["json"]

        def get_transcription_uri(transcription_files : Dict, user_config : helper.Read_Only_Dict) -> str :
    # Get Transcription Files JSON response sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/GetTranscriptionFiles
            value = next(filter(lambda value: "transcription" == value["kind"].lower(), transcription_files["values"]), None)    
            if value is None :
                raise Exception (f"Unable to parse response from Get Transcription Files API:{linesep}{transcription_files['text']}")
            return value["links"]["contentUrl"]

        def get_transcription(transcription_uri : str) -> Dict :
            response = rest_helper.send_get(uri=transcription_uri, key="", expected_status_codes=[HTTPStatus.OK])
            return response["json"]

        def get_transcription_phrases(transcription : Dict, user_config : helper.Read_Only_Dict) -> List[TranscriptionPhrase] :
            def helper(id_and_phrase : Tuple[int, Dict]) -> TranscriptionPhrase :
                (id, phrase) = id_and_phrase
                best = phrase["nBest"][0]
                speaker_number : int
        # If the user specified stereo audio, and therefore we turned off diarization,
        # only the channel property is present.
        # Note: Channels are numbered from 0. Speakers are numbered from 1.
                if "speaker" in phrase :
                    speaker_number = phrase["speaker"] - 1
                elif "channel" in phrase :
                    speaker_number = phrase["channel"]
                else :
                    raise Exception(f"nBest item contains neither channel nor speaker attribute.{linesep}{best}")
                return TranscriptionPhrase(id, best["display"], best["itn"], best["lexical"], speaker_number, phrase["offset"], phrase["offsetInTicks"])
    # For stereo audio, the phrases are sorted by channel number, so resort them by offset.
            return list(map(helper, enumerate(transcription["recognizedPhrases"])))

        def delete_transcription(transcription_id : str, user_config : helper.Read_Only_Dict) -> None :
            uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}"
            rest_helper.send_delete(uri=uri, key=user_config["speech_subscription_key"], expected_status_codes=[HTTPStatus.NO_CONTENT])

        def get_sentiments_helper(documents : List[Dict], user_config : helper.Read_Only_Dict) -> Dict :
            uri = f"https://{user_config['language_endpoint']}{SENTIMENT_ANALYSIS_PATH}{SENTIMENT_ANALYSIS_QUERY}"
            content = {
                "kind" : "SentimentAnalysis",
                "analysisInput" : { "documents" : documents },
                }
            response = rest_helper.send_post(uri = uri, content=content, key=user_config["language_subscription_key"], expected_status_codes=[HTTPStatus.OK])
            return response["json"]["results"]["documents"]

        def get_sentiment_analysis(phrases : List[TranscriptionPhrase], user_config : helper.Read_Only_Dict) -> List[SentimentAnalysisResult] :
            retval : List[SentimentAnalysisResult] = []
    # Create a map of phrase ID to phrase data so we can retrieve it later.
            phrase_data : Dict = {}
    # Convert each transcription phrase to a "document" as expected by the sentiment analysis REST API.
    # Include a counter to use as a document ID.
            documents : List[Dict] = []
            for phrase in phrases :
                phrase_data[phrase.id] = (phrase.speaker_number, phrase.offset_in_ticks)
                documents.append({
                    "id" : phrase.id,
                    "language" : user_config["language"],
                    "text" : phrase.text,
                })
    # We can only analyze sentiment for 10 documents per request.
    # Get the sentiments for each chunk of documents.
            result_chunks = list(map(lambda xs : get_sentiments_helper(xs, user_config), helper.chunk (documents, 10)))
            for result_chunk in result_chunks :
                for document in result_chunk :
                    retval.append(SentimentAnalysisResult(phrase_data[int(document["id"])][0], phrase_data[int(document["id"])][1], document))
            return retval

        def get_sentiments_for_simple_output(sentiment_analysis_results : List[SentimentAnalysisResult]) -> List[str] :
            sorted_by_offset = sorted(sentiment_analysis_results, key=lambda x : x.offset_in_ticks)
            return list(map(lambda result : result.document["sentiment"], sorted_by_offset))

        def get_sentiment_confidence_scores(sentiment_analysis_results : List[SentimentAnalysisResult]) -> List[Dict] :
            sorted_by_offset = sorted(sentiment_analysis_results, key=lambda x : x.offset_in_ticks)
            return list(map(lambda result : result.document["confidenceScores"], sorted_by_offset))

        def merge_sentiment_confidence_scores_into_transcription(transcription : Dict, sentiment_confidence_scores : List[Dict]) -> Dict :
            for id, phrase in enumerate(transcription["recognizedPhrases"]) :
                for best_item in phrase["nBest"] :
                    best_item["sentiment"] = sentiment_confidence_scores[id]
            return transcription

        def transcription_phrases_to_conversation_items(phrases : List[TranscriptionPhrase]) -> List[Dict] :
            return [{
                "id" : phrase.id,
                "text" : phrase.text,
                "itn" : phrase.itn,
                "lexical" : phrase.lexical,
        # The first person to speak is probably the agent.
                "role" : "Agent" if 0 == phrase.speaker_number else "Customer",
                "participantId" : phrase.speaker_number
            } for phrase in phrases]

        def request_conversation_analysis(conversation_items : List[Dict], user_config : helper.Read_Only_Dict) -> str :
            uri = f"https://{user_config['language_endpoint']}{CONVERSATION_ANALYSIS_PATH}{CONVERSATION_ANALYSIS_QUERY}"
            content = {
                "displayName" : f"call_center_{datetime.now()}",
                "analysisInput" : {
                    "conversations" : [{
                        "id" : "conversation1",
                        "language" : user_config["language"],
                        "modality" : "transcript",
                        "conversationItems" : conversation_items,
                    }],
                },
                "tasks" : [
                    {
                        "taskName" : "summary_1",
                        "kind" : "ConversationalSummarizationTask",
                        "parameters" : {
                            "summaryAspects" : ["Issue"]
                        }
                    },
                    {
                        "taskName" : "summary_2",
                        "kind" : "ConversationalSummarizationTask",
                        "parameters" : {
                            "summaryAspects" : ["resolution"],
                            "sentenceCount" : 1
                        }
                    },
                    {
                        "taskName" : "PII_1",
                        "kind" : "ConversationalPIITask",
                        "parameters" : {
                            "piiCategories" : [
                                "All",
                            ],
                            "includeAudioRedaction" : False,
                            "redactionSource" : "text",
                            "modelVersion" : CONVERSATION_SUMMARY_MODEL_VERSION,
                            "loggingOptOut" : False
                        }
                    }
                ]
            }
            response = rest_helper.send_post(uri=uri, content=content, key=user_config["language_subscription_key"], expected_status_codes=[HTTPStatus.ACCEPTED])
            return response["headers"]["operation-location"]

        def get_conversation_analysis_status(conversation_analysis_url : str, user_config : helper.Read_Only_Dict) -> bool :
            response = rest_helper.send_get(uri=conversation_analysis_url, key=user_config["language_subscription_key"], expected_status_codes=[HTTPStatus.OK])
            if "failed" == response["json"]["status"].lower() :
                raise Exception(f"Unable to analyze conversation. Response:{linesep}{response['text']}")
            else :
                return "succeeded" == response["json"]["status"].lower()

        def wait_for_conversation_analysis(conversation_analysis_url : str, user_config : helper.Read_Only_Dict) -> None :
            done = False
            while not done :
                print(f"Waiting {WAIT_SECONDS} seconds for conversation analysis to complete.")
                with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Waiting {WAIT_SECONDS} seconds for conversation analysis to complete." + "\n")
                sleep(WAIT_SECONDS)
                done = get_conversation_analysis_status(conversation_analysis_url, user_config=user_config)

        def get_conversation_analysis(conversation_analysis_url : str, user_config : helper.Read_Only_Dict) -> Dict :
            response = rest_helper.send_get(uri=conversation_analysis_url, key=user_config["language_subscription_key"], expected_status_codes=[HTTPStatus.OK])
            return response["json"]

        def get_conversation_analysis_for_simple_output(conversation_analysis : Dict, user_config : helper.Read_Only_Dict) -> ConversationAnalysisForSimpleOutput :
            tasks = conversation_analysis["tasks"]["items"]
    
            summary_task = next(filter(lambda task : "summary_1" == task["taskName"], tasks), None)
            if summary_task is None :
                raise Exception (f"Unable to parse response from Get Conversation Analysis API. Summary task missing. Response:{linesep}{conversation_analysis}")
            conversation = summary_task["results"]["conversations"][0]
            summary_items = list(map(lambda summary : ConversationAnalysisSummaryItem(summary["aspect"], summary["text"]), conversation["summaries"]))

            summary_task1 = next(filter(lambda task : "summary_2" == task["taskName"], tasks), None)
            if summary_task1 is None :
                raise Exception (f"Unable to parse response from Get Conversation Analysis API. Summary task missing. Response:{linesep}{conversation_analysis}")
            conversation = summary_task1["results"]["conversations"][0]
            summary_items = list(map(lambda summary : ConversationAnalysisSummaryItem(summary["aspect"], summary["text"]), conversation["summaries"]))

            pii_task = next(filter(lambda task : "PII_1" == task["taskName"], tasks), None)
            if pii_task is None :
                raise Exception (f"Unable to parse response from Get Conversation Analysis API. PII task missing. Response:{linesep}{conversation_analysis}")
            conversation = pii_task["results"]["conversations"][0]
            pii_items = [[ConversationAnalysisPiiItem(entity["category"], entity["text"])
                for entity in conversation_item["entities"]]
                for conversation_item in conversation["conversationItems"]]

            return ConversationAnalysisForSimpleOutput(summary_items, pii_items)

        def get_simple_output(phrases : List[TranscriptionPhrase], sentiments : List[str], conversation_analysis : ConversationAnalysisForSimpleOutput) -> str :
            result = ""
            for index, phrase in enumerate(phrases) :
                result += f"Phrase: {phrase.text}{linesep}"
                result += f"Speaker: {phrase.speaker_number}{linesep}"
                if index < len(sentiments) :
                    result += f"Sentiment: {sentiments[index]}{linesep}"
                if index < len(conversation_analysis.pii_analysis) :
                    if len(conversation_analysis.pii_analysis[index]) > 0 :
                        entities = reduce(lambda acc, entity : f"{acc}    Category: {entity.category}. Text: {entity.text}.{linesep}", conversation_analysis.pii_analysis[index], "")
                        result += f"Recognized entities (PII):{linesep}{entities}"
                    else :
                        result += f"Recognized entities (PII): none.{linesep}"
                result += linesep
            result += reduce(lambda acc, item : f"{acc}    {item.aspect}: {item.summary}.{linesep}", conversation_analysis.summary, f"Conversation summary:{linesep}")
            return result

        def print_simple_output(phrases : List[TranscriptionPhrase], sentiment_analysis_results : List[SentimentAnalysisResult], conversation_analysis : Dict, user_config : helper.Read_Only_Dict) -> None :
            sentiments = get_sentiments_for_simple_output(sentiment_analysis_results)
            conversation = get_conversation_analysis_for_simple_output(conversation_analysis, user_config)
            print(get_simple_output(phrases, sentiments, conversation))

        def get_conversation_analysis_for_full_output(phrases : List[TranscriptionPhrase], conversation_analysis : Dict) -> Dict :
    # Get the conversation summary and conversation PII analysis task results.
            tasks = conversation_analysis["tasks"]["items"]
            conversation_summary_results = next(filter(lambda task : "summary_1" == task["taskName"], tasks))["results"]
            conversation_summary_results1 = next(filter(lambda task : "summary_2" == task["taskName"], tasks))["results"]
            conversation_pii_results = next(filter(lambda task : "PII_1" == task["taskName"], tasks))["results"]
    # There should be only one conversation.
            conversation = conversation_pii_results["conversations"][0]
    # Order conversation items by ID so they match the order of the transcription phrases.
            conversation["conversationItems"] = sorted(conversation["conversationItems"], key=lambda item : int(item["id"]))
            combined_redacted_content = [get_combined_redacted_content(0), get_combined_redacted_content(1)]
            for index, conversation_item in enumerate(conversation["conversationItems"]) :
        # Get the channel and offset for this conversation item from the corresponding transcription phrase.
                channel = phrases[index].speaker_number
        # Add channel and offset to conversation item JsonElement.
                conversation_item["channel"] = channel
                conversation_item["offset"] = phrases[index].offset
        # Get the text, lexical, and itn fields from redacted content, and append them to the combined redacted content for this channel.
                redacted_content = conversation_item["redactedContent"]
                combined_redacted_content[channel]["display"] += f"{redacted_content['text']} "
                combined_redacted_content[channel]["lexical"] += f"{redacted_content['lexical']} "
                combined_redacted_content[channel]["itn"] += f"{redacted_content['itn']} "
            return {
                "conversationSummaryResults" : conversation_summary_results,
                "conversationSummaryResults1" : conversation_summary_results1,
                "conversationPiiResults" : {
                    "combinedRedactedContent" : combined_redacted_content,
                    "conversations" : [conversation]
                }
            }

 #validate json object
        def validate_string(val):
            if val != None:
                if type(val) is int:
                    return str(val).encode('utf-8')
                else:
                    return val

        def print_full_output(output_file_path : str, transcription : Dict, sentiment_confidence_scores : List[Dict], phrases : List[TranscriptionPhrase], conversation_analysis : Dict) -> None :
            results = {
                "transcription" : merge_sentiment_confidence_scores_into_transcription(transcription, sentiment_confidence_scores),
                "conversationAnalyticsResults" : get_conversation_analysis_for_full_output(phrases, conversation_analysis)
            }
            with open(output_file_path, mode = "w", newline = "") as f :
                f.write(dumps(results, indent=2))

        def print_full_output_sql(transcription : Dict, sentiment_confidence_scores : List[Dict], phrases : List[TranscriptionPhrase], conversation_analysis : Dict) -> None :
            results = {
                "transcription" : merge_sentiment_confidence_scores_into_transcription(transcription, sentiment_confidence_scores),
                "conversationAnalyticsResults" : get_conversation_analysis_for_full_output(phrases, conversation_analysis)
            }
    #read the JSON File
            json_obj1 = json.dumps(results)
            json_obj = json.loads(json_obj1)
     
#Connect to the SQL Database
            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Connecting to SQL DB"  + "\n")
            conn = pymysql.connect(host=MYSQL_SERVER_NAME, user=MYSQL_SERVER_UNAME, password=MYSQL_SERVER_PASS, db=MYSQL_SERVER_DB, ssl={"fake_flag_to_enable_tls":True})
            cursor = conn.cursor()


#parse json in to sql
            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Write Phrases."  + "\n")
            transcription_obj = json_obj["transcription"]
            runningname=transcription_obj["source"]
            phrases_array = transcription_obj["recognizedPhrases"]
            for i, phrases_obj in enumerate(phrases_array):
                channel1 = validate_string(phrases_obj["channel"])
                speaker1 = validate_string(phrases_obj["speaker"])
                offset1 = validate_string(phrases_obj["offset"])
                lexical1 = validate_string(phrases_obj["nBest"][0]["lexical"])
                itn1 = validate_string(phrases_obj["nBest"][0]["itn"])
                maskedITN1 = validate_string(phrases_obj["nBest"][0]["maskedITN"])
                display1 = validate_string(phrases_obj["nBest"][0]["display"])
                pos = validate_string(phrases_obj["nBest"][0]["sentiment"]["positive"])
                neu = validate_string(phrases_obj["nBest"][0]["sentiment"]["neutral"])
                neg = validate_string(phrases_obj["nBest"][0]["sentiment"]["negative"])
                cursor.execute("INSERT INTO testv2 (channel,speaker, offset, lexical, itn, maskedITN, display,name,sentpos,sentneg,sentneu) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(channel1, speaker1, offset1, lexical1, itn1, maskedITN1, display1, runningname,pos,neg,neu))

                endpoint = CONN_ENDPOINT
                key = CONN_KEY

                documents = [display1]
                text_analytics_client = TextAnalyticsClient(
                    endpoint=endpoint,
                    credential=AzureKeyCredential(key),
                )
                poller = text_analytics_client.begin_analyze_healthcare_entities(documents)
                result = poller.result()

                docs = [doc for doc in result if not doc.is_error]
                for doc in docs:
                    for entity in doc.entities:
                        TAEntity = (f"Entity: {entity.text}")
                        TANorm = (f"...Normalized Text: {entity.normalized_text}")
                        TACat = (f"...Category: {entity.category}")
                        TASCat = (f"...Subcategory: {entity.subcategory}")
                        TAOffset = (f"...Offset: {entity.offset}")
                        TACscore = (f"...Confidence score: {entity.confidence_score}")
                        sqlQueryTA="INSERT INTO testv2ta (TAEntity,TANorm,TACat,TASCat,TAOffset,TACscore,name,TASet) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                        sqlAnswersTA = (TAEntity,TANorm,TACat,TASCat,TAOffset,TACscore,runningname,offset1)
                        cursor.execute(sqlQueryTA,sqlAnswersTA)
                        TASet = offset1

                        if entity.data_sources is not None:
                         #print("...Data Sources:")
                            for data_source in entity.data_sources:
                                DSEntitiyID = (f"......Entity ID: {data_source.entity_id}")
                                DSEntiityName = (f"......Name: {data_source.name}")
                                sqlQueryEnt="INSERT INTO taentity (DSEntitiyID,DSEntiityName,offset1,name,text) VALUES (%s,%s,%s,%s,%s)"
                                sqlAnswersEnt = (DSEntitiyID,DSEntiityName,TASet,TANorm,runningname)
                                cursor.execute(sqlQueryEnt,sqlAnswersEnt)


                        if entity.assertion is not None:
                            TAAsser = ("...Assertion:")
                            TAcond = (f"......Conditionality: {entity.assertion.conditionality}")
                            TACert = (f"......Certainty: {entity.assertion.certainty}")
                            TAAssoc = (f"......Association: {entity.assertion.association}")
                            sqlQueryEntA="INSERT INTO taentityass (Assertion,Cond,Cert,Assoc,offset,name) VALUES (%s,%s,%s,%s,%s,%s)"
                            sqlAnswersEntA = (TAAsser,TAcond,TACert,TAAssoc,TASet,runningname)
                            cursor.execute(sqlQueryEntA,sqlAnswersEntA)
                    
                   # for relation in doc.entity_relations:
                   #     TARelType = (f"Relation of type: {relation.relation_type} has the following roles")
                   # for role in relation.roles:
                   #     TARole = (f"...Role '{role.name}' with entity '{role.entity.text}'")

            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Write PII."  + "\n")
            PII_obj = json_obj["conversationAnalyticsResults"]
            PII_array = PII_obj["conversationPiiResults"]
            PII_array1 = PII_array["conversations"][0]["conversationItems"]
            for i, PII_obj1 in enumerate(PII_array1):
                offsetred = validate_string(PII_obj1["offset"])
                itnred = validate_string(PII_obj1["redactedContent"]["itn"])
                lexicalred = validate_string(PII_obj1["redactedContent"]["lexical"])
                textred = validate_string(PII_obj1["redactedContent"]["text"])
                PII_array2 = PII_obj1["entities"]
                for i, PII_obj2 in enumerate(PII_array2):
                    textredent = validate_string(PII_obj2["text"])
                    categoryredent = validate_string(PII_obj2["category"])
                    offsetredent = validate_string(PII_obj2["offset"])
                    lengthredent = validate_string(PII_obj2["length"])

                    sqlQuery1="INSERT INTO testv2n (textredent,categoryredent,offsetredent,lengthredent,offset,Name) VALUES (%s,%s,%s,%s,%s,%s)"
                    sqlAnswers1 = (textredent,categoryredent,offsetredent,lengthredent,offsetred,runningname)
                    cursor.execute(sqlQuery1,sqlAnswers1)

                sqlQuery="UPDATE testv2 SET offsetred=%s,itnred=%s,lexicalred=%s,textred=%s WHERE offset = %s and Name = %s"
                sqlAnswers = (offsetred,itnred,lexicalred,textred,offsetred,runningname)
                cursor.execute(sqlQuery,sqlAnswers)

            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Write PSummary."  + "\n")
            PSummary_obj1 = PII_obj["conversationSummaryResults"]
            PSummary_obj2 = PSummary_obj1["conversations"]
            for i, PSummary_obj3 in enumerate(PSummary_obj2):
                summaryaspect = validate_string(PSummary_obj3["summaries"][0]["aspect"])
                summarytext = validate_string(PSummary_obj3["summaries"][0]["text"])

                sqlQuery2="INSERT INTO testv2s (aspect,text,Name) VALUES (%s,%s,%s)"
                sqlAnswers2=(summaryaspect,summarytext,runningname)
                cursor.execute(sqlQuery2,sqlAnswers2)
            
            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                f.write(f"Write PSummary1."  + "\n")
            PSummary_obj4 = PII_obj["conversationSummaryResults1"]
            PSummary_obj5 = PSummary_obj4["conversations"]
            for i, PSummary_obj6 in enumerate(PSummary_obj5):
                summaryaspectr = validate_string(PSummary_obj6["summaries"][0]["aspect"])
                summarytextr = validate_string(PSummary_obj6["summaries"][0]["text"])

                sqlQueryr="INSERT INTO testv2s (aspect,text,Name) VALUES (%s,%s,%s)"
                sqlAnswersr=(summaryaspectr,summarytextr,runningname)
                cursor.execute(sqlQueryr,sqlAnswersr)

    #Commit changes and close connection
            with open('/home/output/output.txt', mode = "a", newline = "") as f :
                    f.write(f"Close DB Connection."  + "\n")
            conn.commit()
            conn.close()

        def run() -> None :
            usage = """python call_center.py [...]
  HELP
    --help                          Show this help and stop.
  CONNECTION
    --speechKey KEY                 Your Azure Speech service subscription key. Required unless --jsonInput is present.
    --speechRegion REGION           Your Azure Speech service region. Required unless --jsonInput is present.
                                    Examples: westus, eastus
    --languageKey KEY               Your Azure Cognitive Language subscription key. Required.
    --languageEndpoint ENDPOINT     Your Azure Cognitive Language endpoint. Required.
  LANGUAGE
    --language LANGUAGE             The language to use for sentiment analysis and conversation analysis.
                                    This should be a two-letter ISO 639-1 code.
                                    Default: en
    --locale LOCALE                 The locale to use for batch transcription of audio.
                                    Default: en-US
  INPUT
    --input URL                     Input audio from URL. Required unless --jsonInput is present.
    --jsonInput FILE                Input JSON Speech batch transcription result from FILE. Overrides --input.
    --stereo                        Use stereo audio format.
                                    If this is not present, mono is assumed.
  OUTPUT
    --output FILE                   Output phrase list and conversation summary to text file.
"""

            if user_config_helper.cmd_option_exists("--help") :
             print(usage)
            else :
                user_config = user_config_helper.user_config_from_args(usage)
                transcription : Dict
                transcription_id : str
                if user_config["input_file_path"] is not None :
                    with open(user_config["input_file_path"], mode="r") as f :
                        transcription = loads(f.read())
                elif user_config["input_audio_url"] is not None :
            # How to use batch transcription:
            # https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/cognitive-services/Speech-Service/batch-transcription.md
                    transcription_id = create_transcription(user_config)
                    wait_for_transcription(transcription_id, user_config)
                    print(f"Transcription ID: {transcription_id}")
                    with open('/home/output/output.txt', mode = "a", newline = "") as f :
                        f.write(f"Transcription ID: {transcription_id}"  + "\n")
                    transcription_files = get_transcription_files(transcription_id, user_config)
                    transcription_uri = get_transcription_uri(transcription_files, user_config)
                    print(f"Transcription URI: {transcription_uri}")
                    with open('/home/output/output.txt', mode = "a", newline = "") as f :
                        f.write(f"Transcription URI: {transcription_uri}"  + "\n")
                    transcription = get_transcription(transcription_uri)
                else :
                    raise Exception(f"Missing input audio URL.{linesep}{usage}")
        # For stereo audio, the phrases are sorted by channel number, so resort them by offset.
                transcription["recognizedPhrases"] = sorted(transcription["recognizedPhrases"], key=lambda phrase : phrase["offsetInTicks"])
                phrases = get_transcription_phrases(transcription, user_config)
                sentiment_analysis_results = get_sentiment_analysis(phrases, user_config)
                sentiment_confidence_scores = get_sentiment_confidence_scores(sentiment_analysis_results)
                conversation_items = transcription_phrases_to_conversation_items(phrases)
        # NOTE: Conversation summary is currently in gated public preview. You can sign up here:
        # https://aka.ms/applyforconversationsummarization/
                conversation_analysis_url = request_conversation_analysis(conversation_items, user_config)
                wait_for_conversation_analysis(conversation_analysis_url, user_config)
                conversation_analysis = get_conversation_analysis(conversation_analysis_url, user_config)
                #print_simple_output(phrases, sentiment_analysis_results, conversation_analysis, user_config)
                print_full_output_sql(transcription, sentiment_confidence_scores, phrases, conversation_analysis)
                #print_full_output(user_config["output_file_path"], transcription, sentiment_confidence_scores, phrases, conversation_analysis)

        run()
        
        #End of Custom 
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
