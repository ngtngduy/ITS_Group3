
import traci

print("Dang khoi dong SUMO...")

traci.start([
    "sumo",
    "-c", "highway_sparse.sumocfg",
    "--no-step-log", "true"
])

try:
    print("Da ket noi Python voi SUMO!")

    for i in range(10):
        traci.simulationStep()

        print(
            "Thoi gian:", traci.simulation.getTime(),
            "| So xe:", traci.vehicle.getIDCount()
        )

    print("KIEM TRA TRACI THANH CONG!")

finally:
    traci.close()
    print("Da dong SUMO.")
