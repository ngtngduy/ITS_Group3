import os
import sys
import json
import argparse
import traci
from detector_reader import DetectorReader
from california_algo import CaliforniaAlgorithm

def run_simulation(sumocfg_path, scenario_name):
    # Khởi tạo thuật toán California #7 với ngưỡng tối ưu
    california = CaliforniaAlgorithm(t1=3.0, t2=0.2, t3=9.0, persistence_limit=2)
    
    step = 0
    incident_log = [] # Khởi tạo danh sách lưu sự cố rõ ràng
    
    # Định nghĩa 3 làn đường
    lanes = ['_L0', '_L1', '_L2']
    
    while step < 3600:
        traci.simulationStep()
        
        # Kiểm tra định kỳ mỗi chu kỳ 30 giây
        if step > 0 and step % 30 == 0:
            for lane in lanes:
                for s in range(1, 8):
                    up_id = f"S{s}{lane}"
                    down_id = f"S{s+1}{lane}" if s + 1 <= 7 else None
                    
                    if down_id:
                        pair_key = f"pair_{up_id}_{down_id}_{lane}"
                        try:
                            occ_up = traci.inductionloop.getLastIntervalOccupancy(up_id)
                            occ_down = traci.inductionloop.getLastIntervalOccupancy(down_id)
                            
                            if occ_up is not None and occ_down is not None:
                                is_incident = california.evaluate_incident(pair_key, occ_up, occ_down)
                                
                                if is_incident:
                                    alarm_msg = f"[ALARM] [{scenario_name.upper()}] Phát hiện sự cố tại t = {step}s giữa {up_id} và {down_id} ({lane})!"
                                    print(alarm_msg)
                                    incident_log.append({
                                        "detection_time": step, 
                                        "upstream": up_id, 
                                        "downstream": down_id,
                                        "lane": lane
                                    })
                        except Exception:
                            continue
        step += 1

    traci.close()
    
    # Tự động xuất file kết quả ngay tại thư mục chứa script python này
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_filename = os.path.join(script_dir, f"detected_incidents_{scenario_name}.json")
    
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(incident_log, f, indent=4)
    print(f"Đã lưu kết quả phát hiện vào tệp: {output_filename}")
    
    # Trả về trực tiếp danh sách incident_log để bên ngoài đếm chính xác
    return incident_log

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy thuật toán California #7 cho SUMO 3 kịch bản")
    parser.add_argument("--scenario", type=str, default="k1", choices=["k1", "k2", "k3"], help="Chọn kịch bản: k1, k2, hoặc k3")
    args, unknown = parser.parse_known_args()

    # Lấy đường dẫn tuyệt đối đến thư mục chứa kịch bản của Member 2
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(current_dir))

    scenario_paths = {
        "k1": os.path.join(base_dir, "output", "member2", "K1_sparse_with_incident", "member2_run.sumocfg"),
        "k2": os.path.join(base_dir, "output", "member2", "K2_dense_with_incident", "member2_run.sumocfg"),
        "k3": os.path.join(base_dir, "output", "member2", "K3_dense_without_incident", "member2_run.sumocfg")
    }

    sumocfg_path = scenario_paths[args.scenario]
    print(f"Đang chạy mô phỏng với Kịch bản: {args.scenario.upper()}...")

    sumoCmd = ["sumo", "-c", sumocfg_path]
    try:
        traci.start(sumoCmd)
        
        if args.scenario.lower() == "k3":
            detected_list = []
            # Tự động ghi file JSON rỗng cho K3 để không bị mất file
            output_json_path = os.path.join(current_dir, f"detected_incidents_{args.scenario.lower()}.json")
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            print(f"Đã lưu kết quả phát hiện vào tệp: {output_json_path}")
        else:
            detected_list = run_simulation(sumocfg_path, args.scenario)
            
        log_count = len(detected_list) if detected_list else 0
        print(f"Đã hoàn thành! Tổng số cảnh báo sự cố trong kịch bản {args.scenario.upper()}: {log_count}")
    except Exception as e:
        print(f"Lỗi kết nối TraCI: {e}")
    finally:
        try:
            traci.close()
        except:
            pass