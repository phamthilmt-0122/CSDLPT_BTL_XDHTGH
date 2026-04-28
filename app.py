from flask import Flask, render_template, request, session, redirect, url_for, flash
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
app.secret_key = "fashy_secret_distributed_key"

# --- KẾT NỐI MONGODB ---
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    client.server_info()  # Kiểm tra kết nối
except:
    print("LỖI: Không thể kết nối tới MongoDB. Hãy đảm bảo MongoDB đang chạy!")


# --- HÀM BỔ TRỢ CHỌN DATABASE (SHARDING LOGIC) ---
def get_db_by_region(region_id):
    """Trả về Database tương ứng với phân mảnh miền."""
    mapping = {
        "North": "Logistics_North",
        "Central": "Logistics_Central",
        "South": "Logistics_South"
    }
    db_name = mapping.get(region_id, "Logistics_North")
    return client[db_name]


# --- 1. ROUTE TRANG CHỦ (LANDING PAGE) ---
@app.route('/')
def home():
    """Trang giới thiệu dịch vụ (landing.html)."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


# --- 2. BẢNG ĐIỀU KHIỂN (DASHBOARD) ---
@app.route('/dashboard')
def dashboard():
    """Hiển thị hàng đợi vận đơn dựa trên vai trò người dùng."""
    if 'user_id' not in session:
        return redirect(url_for('login_user'))

    region_id = session.get('region_id')
    user_id = session.get('user_id')
    role = session.get('role')

    db = get_db_by_region(region_id)
    orders = []

    try:
        if role == 'admin':
            # Admin thấy mọi đơn trong Database của miền đó
            orders = list(db.orders.find().sort("created_at", -1))
        elif role in ['warehouse_staff', 'shipper']:
            # Nhân viên thấy đơn thuộc miền quản lý
            orders = list(db.orders.find({"region_id": region_id}).sort("created_at", -1))
        else:
            # Khách hàng thấy đơn của chính mình
            orders = list(db.orders.find({"customer_id": user_id}).sort("created_at", -1))
    except Exception as e:
        print(f"Lỗi truy vấn đơn hàng: {e}")

    return render_template('dashboard.html', orders=orders, role=role)


# --- 3. ĐĂNG NHẬP KHÁCH HÀNG ---
@app.route('/login', methods=['GET', 'POST'])
def login_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Duyệt qua các Shard để tìm khách hàng
        for reg in ["North", "Central", "South"]:
            db = get_db_by_region(reg)
            user = db.users.find_one({"username": username, "password": password, "role": "customer"})
            if user:
                session.clear()  # Đảm bảo session mới hoàn toàn
                session.update({
                    'user_id': user.get('user_id'),
                    'role': 'customer',
                    'region_id': reg,
                    'full_name': user.get('full_name')
                })
                return redirect(url_for('dashboard'))

        flash("Tài khoản khách hàng hoặc mật khẩu không chính xác!", "error")
    return render_template('login_user.html')


# --- 4. ĐĂNG NHẬP NỘI BỘ (STAFF/ADMIN/SHIPPER) ---
@app.route('/internal/login', methods=['GET', 'POST'])
def login_internal():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        region = request.form.get('region')

        db = get_db_by_region(region)
        user = db.users.find_one({"username": username, "password": password, "role": {"$ne": "customer"}})

        if user:
            session.clear()
            session.update({
                'user_id': user.get('user_id'),
                'role': user.get('role'),
                'region_id': region,
                'full_name': user.get('full_name')
            })
            return redirect(url_for('dashboard'))

        flash("Thông tin đăng nhập nội bộ không chính xác!", "error")
    return render_template('login_internal.html')


# --- 5. ĐĂNG KÝ KHÁCH HÀNG ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        region = request.form.get('region')

        db = get_db_by_region(region)

        if db.users.find_one({"username": username}):
            flash("Tên đăng nhập này đã được sử dụng!", "warning")
            return render_template('register.html')

        new_user = {
            "user_id": f"CUST_{datetime.now().strftime('%H%M%S%f')[:10]}",
            "username": username,
            "password": password,
            "role": "customer",
            "full_name": full_name,
            "region_id": region,
            "created_at": datetime.now()
        }
        db.users.insert_one(new_user)
        flash("Đăng ký thành công! Mời bạn đăng nhập.", "success")
        return redirect(url_for('login_user'))
    return render_template('register.html')


# --- 6. ĐĂNG XUẤT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)