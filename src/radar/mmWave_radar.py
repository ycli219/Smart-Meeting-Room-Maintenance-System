'''
# General Library Imports
import copy
import string
import math

# Local Imports
from Demo_Classes.people_tracking import PeopleTracking
from gui_common import NUM_CLASSES_IN_CLASSIFIER, TAG_HISTORY_LEN, CLASSIFIER_CONFIDENCE_SCORE, MIN_CLASSIFICATION_VELOCITY, TAG_HISTORY_LEN, MAX_NUM_UNKNOWN_TAGS_FOR_HUMAN_DETECTION

#
import paho.mqtt.client as mqtt  
import json
import random
MQTT_SERVER = "192.168.0.171" 
MQTT_PORT = 1883  
MQTT_ALIVE = 60  
MQTT_TOPIC = "msg/info"
mqtt_client = mqtt.Client()  
mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)


def publish(data):
  payload = { 
    '# of people': data
  }
  print(f"payload: {payload}")
  mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
  mqtt_client.loop(2,10)

# Logger
import logging
log = logging.getLogger(__name__)

class OOBx432(PeopleTracking):
    def __init__(self):
        PeopleTracking.__init__(self)

    def updateGraph(self, outputDict):
        PeopleTracking.updateGraph(self, outputDict)
        # Update boundary box colors based on results of Occupancy State Machine

        #log.warning("====================================\n")
        #for key, value in outputDict.items():
            #print(f"{key}: {value}")

        if 'numDetectedTracks' in outputDict:
            publish(outputDict['numDetectedTracks'])
        else:
            publish(0)
            
        if ('enhancedPresenceDet' in outputDict):
            enhancedPresenceDet = outputDict['enhancedPresenceDet']
            for box in self.boundaryBoxViz:
                if ('mpdBoundary' in box['name']):
                    # Get index of the occupancy zone from the box name
                    boxIdx = int(box['name'].lstrip(string.ascii_letters))
                    # out of bounds

                    if (boxIdx >= len(enhancedPresenceDet)):
                        log.warning("Warning : Occupancy results for box that does not exist")
                    elif (enhancedPresenceDet[boxIdx] == 0):
                        self.changeBoundaryBoxColor(box, 'b') # Zone unoccupied
                    elif (enhancedPresenceDet[boxIdx] == 1):
                        self.changeBoundaryBoxColor(box, 'y') # Minor Motion Zone Occupancy 
                    elif (enhancedPresenceDet[boxIdx] == 2):
                        self.changeBoundaryBoxColor(box, 'r') # Major Motion Zone Occupancy
                    else:
                        log.error("Invalid result for Enhanced Presence Detection TLV")

        # Classifier
        for cstr in self.classifierStr:
            cstr.setVisible(False)

        # Hold the track IDs detected in the current frame
        trackIDsInCurrFrame = []
        classifierOutput = None
        tracks = None
        if ('classifierOutput' in outputDict):
            classifierOutput = outputDict['classifierOutput']
        if ('trackData' in outputDict):
            tracks = outputDict['trackData']

        if (classifierOutput is not None and tracks is not None):
            # Loop through the tracks detected to label them as human/non-human
            for trackNum, trackName in enumerate(tracks):
                # Decode trackID from the trackName
                trackID = int(trackName[0])
                # Hold the track IDs detected in the current frame
                trackIDsInCurrFrame.append(trackID)
                # Track Velocity (radial) = (x * v_x + y*v_y + z*v_z)/ r
                trackVelocity = (trackName[1] * trackName[4] + trackName[2] * trackName[5] + trackName[3] * trackName[6]) \
                / math.sqrt(math.pow(trackName[1], 2) + math.pow(trackName[2], 2) + math.pow(trackName[3], 2))
                
                # Update the tags if ((classification probabilities have been generated by the radar for the current frame) AND 
                # (either the target has not already been detected as a human or the doppler is above the minimum velocity for classification)). 
                # This is designed to stop the tags from being assigned if target has already been detected as a human and becomes stationary.
                if(classifierOutput[trackNum][0] != 0.5 and not(self.wasTargetHuman[trackID] == 1 and abs(trackVelocity)<MIN_CLASSIFICATION_VELOCITY)):
                    # See if either label is above the minimum score needed for classification, it so, add the corresponding tag to the buffer
                    for label in range(NUM_CLASSES_IN_CLASSIFIER):
                        if(classifierOutput[trackNum][label] > CLASSIFIER_CONFIDENCE_SCORE):
                            self.classifierTags[trackID].appendleft(-1 if label == 0 else 1)
                
                # Recompute sum of tags and number of unknown tags
                # Sum the Tags (composed of +1 for one label, -1 for the other label and 0 for unknown) to see which label is dominant
                sumOfTags = sum(self.classifierTags[trackID])
                # Count the number of times there is an unknown tag in the tag buffer
                numUnknownTags = sum(1 for i in self.classifierTags[trackID] if i == 0)

                ## Assign Labels
                # If we don't have enough tags for a decision or the number of tags for human/nonhuman are equal, make no decision 
                if(numUnknownTags > MAX_NUM_UNKNOWN_TAGS_FOR_HUMAN_DETECTION or sumOfTags == 0):
                    self.wasTargetHuman[trackID] = 0 # Target was NOT detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Unknown Label")
                # If we have enough tags and the majority of them are for nonhuman, then detect nonhuman
                elif(sumOfTags < 0):
                    self.wasTargetHuman[trackID] = 0 # Target was NOT detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Non-Human")
                # If we have enough tags and the majority of them are for human, then detect human
                elif(sumOfTags > 0):
                    self.wasTargetHuman[trackID] = 1 # Target WAS detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Human")
                # Populate string that will display a label      
                self.classifierStr[trackID].setX(trackName[1])
                self.classifierStr[trackID].setY(trackName[2])
                self.classifierStr[trackID].setZ(trackName[3] + 0.1) # Add 0.1 so it doesn't interfere with height text if enabled
                self.classifierStr[trackID].setVisible(True) 

            # Regardless of whether you get tracks in the current frame, if there were tracks in the previous frame, reset the
            # tag buffer and wasHumanTarget flag for tracks that aren't detected in the current frame but were detected in the previous frame
            tracksToShuffle = set(self.tracksIDsInPreviousFrame) - set(trackIDsInCurrFrame) 
            for track in tracksToShuffle:
                for frame in range(TAG_HISTORY_LEN):
                    self.classifierTags[track].appendleft(0) # fill the buffer with zeros to remove any history for the track
                self.wasTargetHuman[trackID] = 0 # Since target was not detected in current frame, reset the wasTargetHuman flag
            
            # Put the current tracks detected into the previous track list for the next frame
            self.tracksIDsInPreviousFrame = copy.deepcopy(trackIDsInCurrFrame)
'''


# General Library Imports
import copy
import string
import math

# Local Imports
from Demo_Classes.people_tracking import PeopleTracking
from gui_common import NUM_CLASSES_IN_CLASSIFIER, TAG_HISTORY_LEN, CLASSIFIER_CONFIDENCE_SCORE, MIN_CLASSIFICATION_VELOCITY, TAG_HISTORY_LEN, MAX_NUM_UNKNOWN_TAGS_FOR_HUMAN_DETECTION

#
import paho.mqtt.client as mqtt  
import json
import random
MQTT_SERVER = "172.20.10.8"#"192.168.0.171" 
MQTT_PORT = 1883  
MQTT_ALIVE = 60  
TOPIC_TO_A = "msg/toA"
TOPIC_TO_C = "msg/toC"
color = 'b'

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)

def publish_to_A(data, color):
    payload = { "type": "text", '# of people': data, 'color': color}
    mqtt_client.publish(TOPIC_TO_A, json.dumps(payload), qos=1)
    mqtt_client.loop(2,10)
    print(f"發送給linux: {payload}")

def publish_to_C(data):
    payload = { '# of people': data }
    mqtt_client.publish(TOPIC_TO_C, json.dumps(payload), qos=1)
    mqtt_client.loop(2,10)
    print(f"發送給樹莓派: {payload}")

# Logger
import logging
log = logging.getLogger(__name__)

class OOBx432(PeopleTracking):
    def __init__(self):
        PeopleTracking.__init__(self)

    def updateGraph(self, outputDict):
        PeopleTracking.updateGraph(self, outputDict)
        # Update boundary box colors based on results of Occupancy State Machine

        #log.warning("====================================\n")
        #for key, value in outputDict.items():
            #print(f"{key}: {value}")

        global color
            
        if ('enhancedPresenceDet' in outputDict):
            enhancedPresenceDet = outputDict['enhancedPresenceDet']
            for box in self.boundaryBoxViz:
                if ('mpdBoundary' in box['name']):
                    # Get index of the occupancy zone from the box name
                    boxIdx = int(box['name'].lstrip(string.ascii_letters))
                    # out of bounds

                    if (boxIdx >= len(enhancedPresenceDet)):
                        log.warning("Warning : Occupancy results for box that does not exist")
                    elif (enhancedPresenceDet[boxIdx] == 0):
                        self.changeBoundaryBoxColor(box, 'b') # Zone unoccupied
                        color = 'b'
                    elif (enhancedPresenceDet[boxIdx] == 1):
                        self.changeBoundaryBoxColor(box, 'y') # Minor Motion Zone Occupancy 
                        color = 'y'
                    elif (enhancedPresenceDet[boxIdx] == 2):
                        self.changeBoundaryBoxColor(box, 'r') # Major Motion Zone Occupancy
                        color = 'r'
                    else:
                        log.error("Invalid result for Enhanced Presence Detection TLV")

        if 'numDetectedTracks' in outputDict:
            publish_to_A(outputDict['numDetectedTracks'], color)
            publish_to_C(outputDict['numDetectedTracks'])
        else:
            publish_to_A(0, color)
            publish_to_C(0)

        # Classifier
        for cstr in self.classifierStr:
            cstr.setVisible(False)

        # Hold the track IDs detected in the current frame
        trackIDsInCurrFrame = []
        classifierOutput = None
        tracks = None
        if ('classifierOutput' in outputDict):
            classifierOutput = outputDict['classifierOutput']
        if ('trackData' in outputDict):
            tracks = outputDict['trackData']

        if (classifierOutput is not None and tracks is not None):
            # Loop through the tracks detected to label them as human/non-human
            for trackNum, trackName in enumerate(tracks):
                # Decode trackID from the trackName
                trackID = int(trackName[0])
                # Hold the track IDs detected in the current frame
                trackIDsInCurrFrame.append(trackID)
                # Track Velocity (radial) = (x * v_x + y*v_y + z*v_z)/ r
                trackVelocity = (trackName[1] * trackName[4] + trackName[2] * trackName[5] + trackName[3] * trackName[6]) \
                / math.sqrt(math.pow(trackName[1], 2) + math.pow(trackName[2], 2) + math.pow(trackName[3], 2))
                
                # Update the tags if ((classification probabilities have been generated by the radar for the current frame) AND 
                # (either the target has not already been detected as a human or the doppler is above the minimum velocity for classification)). 
                # This is designed to stop the tags from being assigned if target has already been detected as a human and becomes stationary.
                if(classifierOutput[trackNum][0] != 0.5 and not(self.wasTargetHuman[trackID] == 1 and abs(trackVelocity)<MIN_CLASSIFICATION_VELOCITY)):
                    # See if either label is above the minimum score needed for classification, it so, add the corresponding tag to the buffer
                    for label in range(NUM_CLASSES_IN_CLASSIFIER):
                        if(classifierOutput[trackNum][label] > CLASSIFIER_CONFIDENCE_SCORE):
                            self.classifierTags[trackID].appendleft(-1 if label == 0 else 1)
                
                # Recompute sum of tags and number of unknown tags
                # Sum the Tags (composed of +1 for one label, -1 for the other label and 0 for unknown) to see which label is dominant
                sumOfTags = sum(self.classifierTags[trackID])
                # Count the number of times there is an unknown tag in the tag buffer
                numUnknownTags = sum(1 for i in self.classifierTags[trackID] if i == 0)

                ## Assign Labels
                # If we don't have enough tags for a decision or the number of tags for human/nonhuman are equal, make no decision 
                if(numUnknownTags > MAX_NUM_UNKNOWN_TAGS_FOR_HUMAN_DETECTION or sumOfTags == 0):
                    self.wasTargetHuman[trackID] = 0 # Target was NOT detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Unknown Label")
                # If we have enough tags and the majority of them are for nonhuman, then detect nonhuman
                elif(sumOfTags < 0):
                    self.wasTargetHuman[trackID] = 0 # Target was NOT detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Non-Human")
                # If we have enough tags and the majority of them are for human, then detect human
                elif(sumOfTags > 0):
                    self.wasTargetHuman[trackID] = 1 # Target WAS detected to be human in the current frame, save for next frame
                    self.classifierStr[trackID].setText("Human")
                # Populate string that will display a label      
                self.classifierStr[trackID].setX(trackName[1])
                self.classifierStr[trackID].setY(trackName[2])
                self.classifierStr[trackID].setZ(trackName[3] + 0.1) # Add 0.1 so it doesn't interfere with height text if enabled
                self.classifierStr[trackID].setVisible(True) 

            # Regardless of whether you get tracks in the current frame, if there were tracks in the previous frame, reset the
            # tag buffer and wasHumanTarget flag for tracks that aren't detected in the current frame but were detected in the previous frame
            tracksToShuffle = set(self.tracksIDsInPreviousFrame) - set(trackIDsInCurrFrame) 
            for track in tracksToShuffle:
                for frame in range(TAG_HISTORY_LEN):
                    self.classifierTags[track].appendleft(0) # fill the buffer with zeros to remove any history for the track
                self.wasTargetHuman[trackID] = 0 # Since target was not detected in current frame, reset the wasTargetHuman flag
            
            # Put the current tracks detected into the previous track list for the next frame
            self.tracksIDsInPreviousFrame = copy.deepcopy(trackIDsInCurrFrame)