from __future__ import annotations

from ctypes import Structure, c_float, c_int32, c_wchar
from enum import IntEnum

__all__ = [
    "ACCSessionType",
    "ACCStatus",
    "SPageFileGraphic",
    "SPageFilePhysics",
    "SPageFileStatic",
]


class ACCStatus(IntEnum):
    ACC_OFF = 0
    ACC_REPLAY = 1
    ACC_LIVE = 2
    ACC_PAUSE = 3


class ACCSessionType(IntEnum):
    ACC_UNKNOWN = -1
    ACC_PRACTICE = 0
    ACC_QUALIFY = 1
    ACC_RACE = 2
    ACC_HOTLAP = 3
    ACC_TIME_ATTACK = 4
    ACC_DRIFT = 5
    ACC_DRAG = 6
    ACC_HOTSTINT = 7
    ACC_HOTLAP_SUPERPOLE = 8


WString15 = c_wchar * 15
WString33 = c_wchar * 33
Float2 = c_float * 2
Float3 = c_float * 3
Float4 = c_float * 4
Float5 = c_float * 5
Float60 = c_float * 60
Int60 = c_int32 * 60
WheelContact = Float3 * 4
CarCoordinates = Float3 * 60


class SPageFilePhysics(Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("throttle", c_float),
        ("brake", c_float),
        ("fuel", c_float),
        ("gear", c_int32),
        ("rpms", c_int32),
        ("steerAngle", c_float),
        ("speedKmh", c_float),
        ("velocity", Float3),
        ("accG", Float3),
        ("wheelSlip", Float4),
        ("wheelLoad", Float4),
        ("wheelsPressure", Float4),
        ("wheelAngularSpeed", Float4),
        ("tyreWear", Float4),
        ("tyreDirtyLevel", Float4),
        ("tyreCoreTemperature", Float4),
        ("camberRAD", Float4),
        ("suspensionTravel", Float4),
        ("drs", c_int32),
        ("tc", c_float),
        ("heading", c_float),
        ("pitch", c_float),
        ("roll", c_float),
        ("cgHeight", c_float),
        ("carDamage", Float5),
        ("numberOfTyresOut", c_int32),
        ("pitLimiterOn", c_int32),
        ("abs", c_float),
        ("kersCharge", c_float),
        ("kersInput", c_float),
        ("autoShifterOn", c_int32),
        ("rideHeight", Float2),
        ("turboBoost", c_float),
        ("ballast", c_float),
        ("airDensity", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localAngularVel", Float3),
        ("finalFF", c_float),
        ("performanceMeter", c_float),
        ("engineBrake", c_int32),
        ("ersRecoveryLevel", c_int32),
        ("ersPowerLevel", c_int32),
        ("ersHeatCharging", c_int32),
        ("ersIsCharging", c_int32),
        ("kersCurrentKJ", c_float),
        ("drsAvailable", c_int32),
        ("drsEnabled", c_int32),
        ("brakeTemp", Float4),
        ("clutch", c_float),
        ("tyreTempI", Float4),
        ("tyreTempM", Float4),
        ("tyreTempO", Float4),
        ("isAIControlled", c_int32),
        ("tyreContactPoint", WheelContact),
        ("tyreContactNormal", WheelContact),
        ("tyreContactHeading", WheelContact),
        ("brakeBias", c_float),
        ("localVelocity", Float3),
        ("p2pActivation", c_int32),
        ("p2pStatus", c_int32),
        ("currentMaxRpm", c_int32),
        ("mz", Float4),
        ("fz", Float4),
        ("my", Float4),
        ("slipRatio", Float4),
        ("slipAngle", Float4),
        ("tcInAction", c_int32),
        ("absInAction", c_int32),
        ("suspensionDamage", Float4),
        ("tyreTemp", Float4),
        ("waterTemp", c_float),
        ("brakePressure", Float4),
        ("frontBrakeCompound", c_int32),
        ("rearBrakeCompound", c_int32),
        ("padLife", Float4),
        ("discLife", Float4),
        ("ignitionOn", c_int32),
        ("starterEngineOn", c_int32),
        ("isEngineRunning", c_int32),
        ("kerbVibration", c_float),
        ("slipVibration", c_float),
        ("gVibration", c_float),
        ("absVibration", c_float),
    ]

    @property
    def gas(self) -> float:
        return self.throttle

    @property
    def tyrePressure(self) -> Float4:
        return self.wheelsPressure


class SPageFileGraphic(Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("status", c_int32),
        ("session", c_int32),
        ("currentTime", WString15),
        ("lastTime", WString15),
        ("bestTime", WString15),
        ("split", WString15),
        ("completedLaps", c_int32),
        ("position", c_int32),
        ("iCurrentTime", c_int32),
        ("iLastTime", c_int32),
        ("iBestTime", c_int32),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isInPit", c_int32),
        ("currentSectorIndex", c_int32),
        ("lastSectorTime", c_int32),
        ("numberOfLaps", c_int32),
        ("tyreCompound", WString33),
        ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float),
        ("activeCars", c_int32),
        ("carCoordinates", CarCoordinates),
        ("carId", Int60),
        ("playerCarId", c_int32),
        ("penaltyTime", c_float),
        ("flag", c_int32),
        ("penalty", c_int32),
        ("idealLineOn", c_int32),
        ("isInPitLane", c_int32),
        ("surfaceGrip", c_float),
        ("mandatoryPitDone", c_int32),
        ("windSpeed", c_float),
        ("windDirection", c_float),
        ("isSetupMenuVisible", c_int32),
        ("mainDisplayIndex", c_int32),
        ("secondaryDisplayIndex", c_int32),
        ("tcLevel", c_int32),
        ("tcCutLevel", c_int32),
        ("engineMap", c_int32),
        ("absLevel", c_int32),
        ("fuelPerLap", c_float),
        ("rainLights", c_int32),
        ("flashingLights", c_int32),
        ("lightsStage", c_int32),
        ("exhaustTemperature", c_float),
        ("wiperLV", c_int32),
        ("driverStintTotalTimeLeft", c_int32),
        ("driverStintTimeLeft", c_int32),
        ("rainTyres", c_int32),
        ("sessionIndex", c_int32),
        ("usedFuel", c_float),
        ("deltaLapTime", WString15),
        ("iDeltaLapTime", c_int32),
        ("estimatedLapTime", WString15),
        ("iEstimatedLapTime", c_int32),
        ("isDeltaPositive", c_int32),
        ("iSplit", c_int32),
        ("isValidLap", c_int32),
        ("fuelEstimatedLaps", c_float),
        ("trackStatus", WString33),
        ("missingMandatoryPits", c_int32),
        ("clock", c_float),
        ("directionLightsLeft", c_int32),
        ("directionLightsRight", c_int32),
        ("globalYellow", c_int32),
        ("globalYellow1", c_int32),
        ("globalYellow2", c_int32),
        ("globalYellow3", c_int32),
        ("globalWhite", c_int32),
        ("globalGreen", c_int32),
        ("globalChequered", c_int32),
        ("globalRed", c_int32),
        ("mfdTyreSet", c_int32),
        ("mfdFuelToAdd", c_float),
        ("mfdTyrePressure", Float4),
        ("trackGripStatus", c_int32),
        ("rainIntensity", c_int32),
        ("rainIntensityIn10Min", c_int32),
        ("rainIntensityIn30Min", c_int32),
        ("currentTyreSet", c_int32),
        ("strategyTyreSet", c_int32),
        ("gapAhead", c_int32),
        ("gapBehind", c_int32),
    ]


class SPageFileStatic(Structure):
    _pack_ = 1
    _fields_ = [
        ("smVersion", WString15),
        ("acVersion", WString15),
        ("numberOfSessions", c_int32),
        ("numCars", c_int32),
        ("carModel", WString33),
        ("track", WString33),
        ("playerName", WString33),
        ("playerSurname", WString33),
        ("playerNick", WString33),
        ("_playerNickPadding", c_wchar),
        ("sectorCount", c_int32),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int32),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", Float4),
        ("tyreRadius", Float4),
        ("maxTurboBoost", c_float),
        ("deprecated1", c_float),
        ("deprecated2", c_float),
        ("penaltiesEnabled", c_int32),
        ("aidFuelRate", c_float),
        ("aidTireRate", c_float),
        ("aidMechanicalDamage", c_float),
        ("aidAllowTyreBlankets", c_float),
        ("aidStability", c_float),
        ("aidAutoClutch", c_int32),
        ("aidAutoBlip", c_int32),
        ("hasDRS", c_int32),
        ("hasERS", c_int32),
        ("hasKERS", c_int32),
        ("kersMaxJ", c_float),
        ("engineBrakeSettingsCount", c_int32),
        ("ersPowerControllerCount", c_int32),
        ("trackSplineLength", c_float),
        ("trackConfiguration", WString33),
        ("_trackConfigurationPadding", c_wchar),
        ("ersMaxJ", c_float),
        ("isTimedRace", c_int32),
        ("hasExtraLap", c_int32),
        ("carSkin", WString33),
        ("_carSkinPadding", c_wchar),
        ("reversedGridPositions", c_int32),
        ("pitWindowStart", c_int32),
        ("pitWindowEnd", c_int32),
        ("isOnline", c_int32),
        ("dryTyresName", WString33),
        ("wetTyresName", WString33),
    ]
