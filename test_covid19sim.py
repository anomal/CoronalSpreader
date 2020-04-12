import unittest
import math
import numpy as np
import covid19sim as sim

class TestCovid19Sim(unittest.TestCase):

    def setUp(self):
        sim.populationSize = 2048
        sim.ratioNursesInPopulation = 0.015
        sim.infectiousness = 0.15
        sim.ppeProtection = 0.95
        sim.proportionSevere = 0.2
        sim.proportionSevereCritical = 0.25
        sim.recoveryTime = 18
        sim.fatalityRate = 0.01
        sim.maxPatientsPerNurse = 4
        sim.totalDays = 240
        sim.icuBedsPerHundredThousand = 13.5
        sim.strikeDays = 0
        sim.ppeArrivalDay = 9999999
        sim.prioritizeNursePatient = False
        sim.initPopulation()

    def test_00whenGetExposureResult_expectInfection15(self):
        total = 4000
        count = 0
        severeCount = 0
        criticalCount = 0
        ep = 0.15
        epCrit = 0.2
        for i in range(total):
            severity = sim.getExposureResult(False)
            if severity is not None:
                count += 1
            if severity is sim.Severity.INV_VENT:
                criticalCount += 1
                severeCount += 1
            elif severity is sim.Severity.NONINV_VENT:
                severeCount += 1
        avg = count / total
        isInExpectedRange = avg * (1-ep) < sim.infectiousness and avg * (1+ep) > sim.infectiousness
        if not isInExpectedRange:
            expectedCount = sim.infectiousness * 300
            print("expected avg:", sim.infectiousness, "real avg:", avg, "expected count:", expectedCount, "real count", count)
        self.assertTrue(isInExpectedRange)
        severePerInfected = severeCount / count
        severityIsExpected = severePerInfected * (1-ep) < sim.proportionSevere and severePerInfected * (1+ep) > sim.proportionSevere
        if not severityIsExpected:
            print("expected severity proportion:", sim.proportionSevere, "actual severity proportion:", severePerInfected, \
                "expected severe cases:", count * sim.proportionSevere, "actual severe cases", severeCount)
        self.assertTrue(severityIsExpected)
        criticalPerSevere = criticalCount / severeCount
        criticalIsExpected = criticalPerSevere * (1-epCrit) < sim.proportionSevereCritical and criticalPerSevere * (1+epCrit) > sim.proportionSevereCritical
        if not criticalIsExpected:
            print("expected critical:", sim.proportionSevereCritical, ", actual critical:", criticalPerSevere, \
                ", expected crit count:", sim.proportionSevereCritical * severeCount, ", actual crit count:", criticalCount)
        self.assertTrue(criticalIsExpected)

    def test_00whenAssignNurseAllFullOnly_expectFalse(self):
        sim.initPopulation()
        expectedCapacity = round(sim.ratioNursesInPopulation * sim.populationSize) * sim.maxPatientsPerNurse
        patients = []
        for i in range(expectedCapacity):
            patient = sim.Person(sim.Position(0, i))
            patients.append(patient)
            self.assertTrue(sim.hospital.assignNurse(patient))
        p = sim.Person(sim.Position(0, expectedCapacity))
        self.assertFalse(sim.hospital.assignNurse(p))
        for nurse in sim.hospital.nurses:
           self.assertEqual(sim.maxPatientsPerNurse, len(nurse.patients))
        patients[0].releaseNurse()
        self.assertTrue(sim.hospital.assignNurse(p))
        sim.initPopulation()

    def test_00whenAssignNurseAllFullAndPrioritizeNurse_expectNurseGetsCare(self):
        sim.prioritizeNursePatient = True
        sim.initPopulation()
        expectedCapacity = round(sim.ratioNursesInPopulation * sim.populationSize) * sim.maxPatientsPerNurse
        patients = []
        for i in range(expectedCapacity):
            patient = sim.Person(sim.Position(0, i))
            patients.append(patient)
            patient.infect(sim.Severity.NONINV_VENT)
            self.assertTrue(sim.hospital.assignNurse(patient))
        p = sim.Person(sim.Position(0, expectedCapacity))
        self.assertFalse(sim.hospital.assignNurse(p))
        nurse = sim.Nurse(sim.Position(0, expectedCapacity))
        self.assertTrue(sim.hospital.assignNurse(nurse))
        for nurse in sim.hospital.nurses:
           self.assertEqual(sim.maxPatientsPerNurse, len(nurse.patients))
        sim.prioritizeNursePatient = False
        sim.initPopulation()

    def test_00whenAssignIcuBedToNurseWhenBedFull_expectNurseGetsBed(self):
        sim.prioritizeNursePatient = True
        sim.initPopulation()
        expectedCapacity = sim.getTotalIcuBeds()
        patients = []
        for i in range(expectedCapacity):
            patient = sim.Person(sim.Position(0, i))
            patients.append(patient)
            patient.infect(sim.Severity.INV_VENT)
            self.assertTrue(sim.hospital.assignIcuBed(patient))
        p = sim.Person(sim.Position(0, expectedCapacity))
        self.assertFalse(sim.hospital.assignIcuBed(p))
        nurse = sim.Nurse(sim.Position(0, expectedCapacity))
        nurse.infect(sim.Severity.INV_VENT)
        self.assertTrue(sim.hospital.assignIcuBed(nurse))
        for nonNurse in patients:
           self.assertTrue(nonNurse.isDead())
           self.assertEqual(None, nonNurse.nurse)
           self.assertTrue(nonNurse not in sim.hospital.occupiedBeds)
        self.assertTrue(nurse in sim.hospital.occupiedBeds)
        sim.prioritizeNursePatient = False
        sim.initPopulation()

    def test_01whenRun_expectProgressSequential(self):
        df = sim.run()
        for row in range(sim.height):
           for col in range(sim.width):
               infectedPersonDf = df[(df["x"] == col) & (df["y"] == row) & (df["wasInfected"])]
               infectionDay = infectedPersonDf["day"].min()
               deathDf = infectedPersonDf[infectedPersonDf["isDead"]]
               deathDay = deathDf["day"].min()
               if deathDay is not np.nan:
                   isExpected = infectionDay == deathDay or infectionDay + sim.recoveryTime == deathDay
                   if not isExpected:
                       print(infectedPersonDf)
                       print("deathDay - infectionDay = ", deathDay, "-", infectionDay, "=", deathDay - infectionDay)
                       print(deathDf)
                   self.assertTrue(isExpected)
               else:
                   recoveredDf = infectedPersonDf[infectedPersonDf["isRecovered"]]
                   recoveryDay = recoveredDf["day"].min()
                   if recoveryDay is not np.nan:
                       isExpected = infectionDay + sim.recoveryTime == recoveryDay
                       self.assertTrue(isExpected)

    def test_01whenRun_expectNurseCountLikeProportion(self):
        expectedNurses = round(sim.ratioNursesInPopulation * sim.populationSize) 
        df = sim.run()
        rowCount = df[(df["day"] == 1) & (df["isNurse"])].shape[0]
        self.assertEqual(expectedNurses, rowCount)
        rowCount = df[(df["day"] == sim.totalDays) & (df["isNurse"])].shape[0]
        self.assertEqual(expectedNurses, rowCount)

    def test_02whenRun1Day_expect1Infection(self):
        sim.totalDays = 1
        for i in range(40):
            df = sim.run()
            rowCount = df[df["wasInfected"]].shape[0]
            self.assertEqual(1, rowCount)

    def test_03whenRun1Day_expect1NewlyInfected(self):
        sim.totalDays = 1
        df = sim.run()
        rowCount = df[df["newlyInfected"]].shape[0]
        self.assertEqual(1, rowCount)

    def test_04whenRun2Days100InfectiousSevereCritical_expect3Dead(self):
        sim.totalDays = 2
        sim.infectiousness = 1
        sim.proportionSevere = 1
        sim.proportionSevereCritical = 1
        df = sim.run()
        rowCount = df[df["isDead"]].shape[0]
        self.assertEqual(3, rowCount)

    def test_05when100InfectiousNoNursesDeaths_expectNSquaredInfections(self):
        sim.totalDays = math.floor(sim.height ** 1/2)
        sim.infectiousness = 1
        sim.proportionSevere = 0
        sim.ratioNursesInPopulation = 0
        df = sim.run()
        rowCount = df[df["wasInfected"]].shape[0]
        self.assertTrue(rowCount > 0)
        rowCount = df[(df["day"] == sim.totalDays) & (df["wasInfected"])].shape[0]
        self.assertEqual(sim.totalDays ** 2 + (sim.totalDays - 1) ** 2, rowCount)

if __name__ == '__main__':
    unittest.main()
