import math
from random import random
from enum import Enum
from collections import deque
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

populationSize = 2048
ratioNursesInPopulation = 0.015
infectiousness = 0.15
ppeProtection = 0.95
proportionSevere = 0.2
proportionSevereCritical = 0.25
recoveryTime = 18
fatalityRate = 0.01
maxPatientsPerNurse = 4
totalDays = 240
icuBedsPerHundredThousand = 13.5
totalIcuBeds = max(1, round(populationSize * 13.5/100000))
strikeDays = 0
ppeArrivalDay = 9999999
prioritizeNursePatient = False

# Model

class Outcome(Enum):
    UNINFECTED = "Uninfected"
    INFECTED = "Infected"
    DEAD = "Dead"
    RECOVERED = "Recovered"

class Severity(Enum):
    MILD = "Mild"
    NONINV_VENT = "Hosp, non-inv vent"
    INV_VENT = "Hosp, inv vent"

class Position:

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return str(self.x) + "," + str(self.y)

class Person:

    label = "Regular"

    def __init__(self, position):
        self.position = position
        self.infectionDay = None
        self.outcome = Outcome.UNINFECTED
        self.severity = None
        self.nurse = None

    def __str__(self):
        return str(self.position)

    def isDead(self):
        return self.outcome is Outcome.DEAD

    def isSevere(self):
        return self.severity is Severity.NONINV_VENT or self.severity is Severity.INV_VENT

    def isRecovered(self):
        return self.outcome is Outcome.RECOVERED

    def infect(self, severity):
        if self.outcome is Outcome.UNINFECTED:
            self.outcome = Outcome.INFECTED
            self.severity = severity
            self.infectionDay = 1

    def progress(self):
        self.infectionDay += 1
        if self.isSevere() and self.infectionDay == recoveryTime + 1 and random() * proportionSevere < fatalityRate:
            self.die()
        elif not self.isRecovered() and not self.isDead() and self.infectionDay is not None and self.infectionDay == recoveryTime + 1:
            self.releaseNurse()
            hospital.releaseIcuBed(self)
            self.outcome = Outcome.RECOVERED

    def die(self):
        self.releaseNurse()
        hospital.releaseIcuBed(self)
        self.outcome = Outcome.DEAD

    def releaseNurse(self):
        if self.nurse is not None:
            self.nurse.patients.remove(self)
            self.nurse = None

class Nurse(Person):

    label = "Nurse"

    def __init__(self, position):
        super().__init__(position)
        self.patients = []

    def patientsStr(self):
        s = ""
        for patient in self.patients:
            if s != "":
                s += "; "
            s += str(patient)
        return "{ " + s + " }"

class Hospital:

    def __init__(self, totalIcuBeds):
        self.reset(totalIcuBeds)

    def reset(self, totalIcuBeds):
        self.nurses = deque()
        self.totalIcuBeds = totalIcuBeds
        self.occupiedBeds = set()

    def assignNurse(self, person, kickOutNonNursePatient=False):
        maxedOut = 0
        totalNurses = len(self.nurses)
        
        while maxedOut != totalNurses:
            nurse = self.nurses.popleft()
            self.nurses.append(nurse)
            if not nurse.isDead() and (not nurse.isSevere() or nurse.isRecovered()) and (kickOutNonNursePatient or len(nurse.patients) < maxPatientsPerNurse):
                nurseAvailable = True

                if kickOutNonNursePatient:
                    nonNurse = self.findNonNurse(nurse.patients)
                    if nonNurse is None:
                        nurseAvailable = False
                    else:
                        nonNurse.die()

                if nurseAvailable:
                    nurse.patients.append(person)
                    person.nurse = nurse
                    return True

            else:
                maxedOut += 1

        if not kickOutNonNursePatient and prioritizeNursePatient and isinstance(person, Nurse):
            return self.assignNurse(person, True)
        else:
            return False
    
    def findNonNurse(self, patients):
        for patient in patients:
            if not isinstance(patient, Nurse):
                return patient
        return None

    def assignIcuBed(self, patient):
        bedAvailable = False
        if len(self.occupiedBeds) < self.totalIcuBeds:
            bedAvailable = True
        elif prioritizeNursePatient and isinstance(patient, Nurse):
            nonNurse = self.findNonNurse(self.occupiedBeds)
            if nonNurse is not None:
                nonNurse.die()
                bedAvailable = True
        if bedAvailable:
            self.occupiedBeds.add(patient)
            return True
        else:
            return False

    def releaseIcuBed(self, patient):
        self.occupiedBeds.discard(patient)

hospital = Hospital(totalIcuBeds)
people = []
infected = []

# Functions

def validCoordinate(x, y):
    return x >= 0 and x < width and y >= 0 and y < height

def getNeighbours(person):
    neighbours = []
    for n in [[-1,0], [1,0], [0,-1], [0,1]]:
        x = person.position.x + n[0]
        y = person.position.y + n[1]
        if validCoordinate(x, y):
            index = y * width + x
            neighbour = people[index]
            if neighbour.infectionDay == None:
                neighbours.append(neighbour)
    return neighbours

def getColleagues(nurse):
    colleagues = []
    for n in [-1, 1]:
        x = nurse.position.x * n
        y = nurse.position.y * n
        if (validCoordinate(x,y)):
            index = y * width + x
            colleague = people[index]
            if not isinstance(colleague, Nurse):
                raise ValueError("Wrong coordinates")
            else:
                colleagues.append(colleague)
    return colleagues

def findNurse(patient, strike):
    if strike or not hospital.assignNurse(patient):
        patient.die()

def getExposureResult(hasPpe):
    if hasPpe:
        protection = ppeProtection
    else:
        protection = 0

    chance = random()
    if chance < infectiousness * (1 - protection):
        chanceSevereFromExposure = infectiousness * proportionSevere
        if chance < chanceSevereFromExposure:
            if chance < chanceSevereFromExposure * proportionSevereCritical:
                return Severity.INV_VENT
            else:
                return Severity.NONINV_VENT
        else:
            return Severity.MILD
    else:
        return None

def expose(person, newlyInfected, strike, hasPpe):
    if person.infectionDay == None and not person.isDead() and not person.isRecovered():
        if isinstance(person, Nurse):
            exposureResult = getExposureResult(hasPpe)
        else:
            exposureResult = getExposureResult(False)

        if exposureResult is not None:
            person.infect(exposureResult)
            newlyInfected.append(person)

            if exposureResult is not Severity.MILD:

                if exposureResult is Severity.INV_VENT and not hospital.assignIcuBed(person):
                    person.die()

                if isinstance(person, Nurse):
                    for patient in person.patients.copy():
                        patient.releaseNurse()
                        findNurse(patient, strike)
                    person.patients = []

                if not person.isDead():
                    findNurse(person, strike)

def spread(strike, hasPpe):
    newlyInfected = []
    for person in infected:
        if not person.isDead() and not person.isSevere() and not person.isRecovered():
            neighbours = getNeighbours(person)
            for neighbour in neighbours:
                expose(neighbour, newlyInfected, strike, hasPpe)
        if person.nurse != None:
            expose(person.nurse, newlyInfected, strike, hasPpe)
        elif isinstance(person, Nurse):
            colleagues = getColleagues(person)
            for colleague in colleagues:
                expose(colleague, newlyInfected, strike, hasPpe)
        person.progress()
    infected.extend(newlyInfected)
        
def aggregations(df):
    return df.groupby(["day"]) \
        .sum()[{"wasInfected", "isDead", "isRecovered", "newlyInfected","newlyInfectedSevere","wasInfectedNurse", "isDeadNurse"}] \
        .reset_index() \
        .rename(columns={
            "day" : "Day",
            "wasInfected" : "Total Infections",
            "isDead" : "Total Dead",
            "isRecovered" : "Total Recovered",
            "newlyInfected" : "New Infections",
            "newlyInfectedSevere" : "New Infections Requiring Hospitalization",
            "wasInfectedNurse" : "Total Nurse Infections",
            "isDeadNurse" : "Total Nurses Dead"
    })

def run():
    data = {}
    initPopulation()
    collectData(data, 1)
    for i in range(1, totalDays):
        spread(i <= strikeDays, i >= ppeArrivalDay)
        collectData(data, i + 1)
    return pd.DataFrame(data=data)

def collectData(data, day):
    if data.get("day", None) is None:
        data["day"] = []
        data["id"] = []
        data["legend"] = []
        data["x"] = []
        data["y"] = []
        data["isNurse"] = []
        data["severity"] = []
        data["isDead"] = []
        data["isRecovered"] = []
        data["wasInfected"] = []
        data["newlyInfected"] = []
        data["newlyInfectedSevere"] = []
        data["wasInfectedNurse"] = []
        data["isDeadNurse"] = []
    for person in people:
        data["day"].append(day)
        data["id"].append(str(person))
        data["legend"].append(legend(person)) 
        data["x"].append(person.position.x)  
        data["y"].append(person.position.y)  
        data["isNurse"].append(isinstance(person,Nurse))
        if person.severity is None:
            severityValue = "N/A"
        else:
            severityValue = person.severity.value
        data["severity"].append(severityValue)
        data["isDead"].append(person.isDead())
        data["isRecovered"].append(person.isRecovered())
        data["wasInfected"].append(person.outcome is not Outcome.UNINFECTED)
        data["newlyInfected"].append(person.infectionDay == 1)
        data["newlyInfectedSevere"].append(person.infectionDay == 1 and person.isSevere())
        data["wasInfectedNurse"].append(isinstance(person,Nurse) and person.outcome is not Outcome.UNINFECTED)
        data["isDeadNurse"].append(isinstance(person,Nurse) and person.isDead())
width = 64
height = math.floor(populationSize / width)

def initPopulation():
    people.clear()
    infected.clear()
    hospital.reset(totalIcuBeds)
    
    for i in range(0, populationSize):
        position = Position(i % width, math.floor(i / width))

        if ratioNursesInPopulation != 0 and i % round(1/ratioNursesInPopulation) == 0:
            person = Nurse(position)
            hospital.nurses.append(person)
        else:
            person = Person(position)
        if i == math.floor(populationSize / 2) + math.floor(width / 2) :
            person.infect(Severity.MILD)
            infected.append(person)
        people.append(person)

sNurse = "Nurse"

def legend(person):

    legend = person.label

    if person.outcome is Outcome.UNINFECTED:
        legend += " " + Outcome.UNINFECTED.value
    elif person.isDead():
        legend += " " + Outcome.DEAD.value
    elif person.isRecovered():
        legend += " " + Outcome.RECOVERED.value
    else: 
        if person.severity is not None:
            legend += " " + person.severity.value
        else:
            raise ValueError(person, "is infected but with no severity")

    return legend

def styleMarker(datum):
    if (Nurse.label in datum.name): 
        datum.marker.symbol = "cross"
        if Severity.MILD.value in datum.name:
            datum.marker.color = "orange"
        elif Severity.INV_VENT.value in datum.name:
            datum.marker.color = "purple"
        elif Severity.NONINV_VENT.value in datum.name:
            datum.marker.color = "red"
        elif Outcome.DEAD.value in datum.name:
            datum.marker.color = "white"
        elif Outcome.RECOVERED.value in datum.name:
            datum.marker.color = "green"
        else:
            datum.marker.color = "blue"
    else:
        if Severity.MILD.value in datum.name:
            datum.marker.color = "navajowhite"
        elif Severity.INV_VENT.value in datum.name:
            datum.marker.color = "mediumpurple"
        elif Severity.NONINV_VENT.value in datum.name:
            datum.marker.color = "darksalmon"
        elif Outcome.DEAD.value in datum.name:
            datum.marker.color = "black"
        elif Outcome.RECOVERED.value in datum.name:
            datum.marker.color = "lightgreen"
        else:
            datum.marker.color = "lightskyblue"

def showSpread(df, day):
    dfDay = df[df["day"] == day]
    fig = px.scatter(dfDay, x="x", y="y", color="legend")
    for d in fig['data']:
        styleMarker(d)
    fig.show()

