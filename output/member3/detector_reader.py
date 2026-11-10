import traci

class DetectorReader:
    def __init__(self, detector_ids=None):
        if detector_ids is None:
            self.detector_ids = ['S1_L0', 'S2_L0', 'S3_L0', 'S4_L0', 'S5_L0', 'S6_L0', 'S7_L0']
        else:
            self.detector_ids = detector_ids

    def get_current_occupancy(self):
        occupancy_data = {}
        for det_id in self.detector_ids:
            try:
                # Lấy độ chiếm dụng tính bằng phần trăm (%) trong khoảng thời gian đo gần nhất
                occ = traci.inductionloop.getLastIntervalOccupancy(det_id)
                occupancy_data[det_id] = occ
            except Exception as e:
                # Trường hợp cảm biến chưa thu thập dữ liệu hoặc lỗi kết nối
                occupancy_data[det_id] = 0.0
                
        return occupancy_data

    def get_upstream_downstream_pair(self, i):
        if i + 1 < len(self.detector_ids):
            up_id = self.detector_ids[i]      # Trạm i (Thượng lưu)
            down_id = self.detector_ids[i+1]  # Trạm i+1 (Hạ lưu)
            
            occ_up = traci.inductionloop.getLastIntervalOccupancy(up_id)
            occ_down = traci.inductionloop.getLastIntervalOccupancy(down_id)
            
            return occ_up, occ_down
        return None, None