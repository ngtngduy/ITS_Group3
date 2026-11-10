class CaliforniaAlgorithm:
    def __init__(self, t1=8.0, t2=0.39, t3=9.0, persistence_limit=2):
        self.t1 = t1
        self.t2 = t2
        self.t3 = t3
        self.persistence_limit = persistence_limit
        
        # Bộ đếm duy trì trạng thái cho từng cặp cảm biến (Key: cặp cảm biến, Value: số đếm)
        self.counter_p = {}

    def evaluate_incident(self, pair_key, occ_up, occ_down):
        # Khởi tạo bộ đếm cho cặp cảm biến nếu chưa có
        if pair_key not in self.counter_p:
            self.counter_p[pair_key] = 0

        # Tránh lỗi chia cho 0 nếu occ_up bằng 0
        if occ_up <= 0:
            self.counter_p[pair_key] = max(0, self.counter_p[pair_key] - 1)
            return False

        #3 BƯỚC LỌC TUẦN TỰ
        # 1
        occdf = occ_up - occ_down
        
        # 2
        occrdf = (occ_up - occ_down) / occ_up
        
        # 3
        cond3 = occ_down < self.t3

        # Kiểm tra đồng thời 3 điều kiện ngưỡng
        is_matched = (occdf > self.t1) and (occrdf > self.t2) and cond3

        #PERSISTANCE TEST
        if is_matched:
            # Tăng bộ đếm nếu thỏa mãn điều kiện trong chu kỳ này
            self.counter_p[pair_key] += 1
        else:
            # Giảm bộ đếm dần nếu không còn thỏa mãn
            self.counter_p[pair_key] = max(0, self.counter_p[pair_key] - 1)

        # Nếu số chu kỳ liên tiếp vượt ngưỡng đạt đến giới hạn P -> Xác nhận có sự cố thực sự
        if self.counter_p[pair_key] >= self.persistence_limit:
            return True

        return False