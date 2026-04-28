from pymongo import MongoClient
from datetime import datetime

# Kết nối tới MongoDB Local (Trong thực tế sẽ là 3 IP khác nhau)
client = MongoClient("mongodb://localhost:27017/")

# Danh sách các Database theo miền
regions = {
    "North": client["Logistics_North"],
    "Central": client["Logistics_Central"],
    "South": client["Logistics_South"]
}


def init_databases():
    for region_name, db in regions.items():
        print(f"--- Đang khởi tạo Database cho miền: {region_name} ---")

        # 1. Làm sạch dữ liệu cũ
        db.orders.drop()
        db.users.drop()
        db.warehouses.drop()

        # 2. Tạo bảng Users (Phân quyền & Đối tượng)
        # Lưu ý: Mỗi miền sẽ có danh sách nhân viên riêng của miền đó
        users_sample = [
            {
                "user_id": f"ADMIN_{region_name}",
                "username": f"admin_{region_name.lower()}",
                "password": "123", "role": "admin",
                "full_name": f"Quản trị viên miền {region_name}"
            },
            {
                "user_id": f"STAFF_{region_name}_01",
                "username": f"staff_{region_name.lower()}",
                "password": "123", "role": "warehouse_staff",
                "warehouse_id": f"WH_{region_name}_01",
                "full_name": f"Nhân viên kho {region_name}"
            },
            {
                "user_id": f"SHIPPER_{region_name}_01",
                "username": f"shipper_{region_name.lower()}",
                "password": "123", "role": "shipper",
                "full_name": f"Shipper miền {region_name}"
            },
            {
                "user_id": f"CUST_{region_name}_01",
                "username": f"user_{region_name.lower()}",
                "password": "123", "role": "customer",
                "full_name": f"Khách hàng {region_name}"
            }
        ]
        db.users.insert_many(users_sample)

        # 3. Tạo bảng Warehouses (Danh mục kho bãi bưu cục)
        warehouses_sample = [
            {
                "warehouse_id": f"WH_{region_name}_01",
                "name": f"Kho tổng miền {region_name}",
                "address": f"Trung tâm miền {region_name}",
                "type": "HUB"
            }
        ]
        db.warehouses.insert_many(warehouses_sample)

        # 4. Tạo bảng Orders (Vận đơn)
        # Giả sử có 1 đơn hàng khởi tạo tại miền này
        order_sample = {
            "order_id": f"ORD_{region_name}_001",
            "customer_id": f"CUST_{region_name}_01",
            "region_id": region_name,
            "status": "Pending",  # Trạng thái: Chờ lấy hàng, Nhập kho, Đang giao, Hoàn đơn
            "sender": {"name": "Người gửi mẫu", "address": f"Địa chỉ tại {region_name}"},
            "receiver": {"name": "Người nhận mẫu", "address": "Địa chỉ nhận hàng"},
            "package": {"weight": 2.0, "cod": 500000},
            "current_location": {"warehouse_id": f"WH_{region_name}_01", "time": datetime.now()},
            "tracking_logs": [
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "Hệ thống",
                    "action": "Khởi tạo đơn hàng",
                    "staff_id": "System"
                }
            ]
        }
        db.orders.insert_one(order_sample)

    print("\n[SUCCESS] Đã tạo xong 3 Database phân tán: North, Central, South.")


if __name__ == "__main__":
    init_databases()