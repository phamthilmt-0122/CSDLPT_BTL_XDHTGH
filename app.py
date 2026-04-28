from flask import Flask, render_template, request, session, redirect, url_for, flash
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
app.secret_key = "fashy_secret_distributed_key"

# --- KẾT NỐI MONGODB ---
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    client.server_info()
except:
    print("LỖI: Không thể kết nối tới MongoDB. Hãy đảm bảo service MongoDB đang chạy!")


# --- HÀM CHỌN DATABASE THEO MIỀN (SHARDING LOGIC) ---
def get_db_by_region(region_id):
    mapping = {
        "North": "Logistics_North",
        "Central": "Logistics_Central",
        "South": "Logistics_South"
    }
    db_name = mapping.get(region_id, "Logistics_North")
    return client[db_name]


# --- 1. TRANG CHỦ (LANDING) ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


# --- 2. BẢNG ĐIỀU KHIỂN (DASHBOARD - HÀNG ĐỢI VẬN ĐƠN) ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_user'))

    region_id = session.get('region_id')
    user_id = session.get('user_id')
    role = session.get('role')

    db = get_db_by_region(region_id)
    orders = []

    try:
        if role == 'admin':
            # Admin xem mọi đơn trong Shard hiện tại
            orders = list(db.orders.find().sort("created_at", -1))
        elif role in ['warehouse_staff', 'shipper']:
            # Nhân viên xem đơn trong miền quản lý
            orders = list(db.orders.find({"region_id": region_id}).sort("created_at", -1))
        else:
            # Khách hàng xem đơn của chính mình (Hàng đợi cá nhân)
            orders = list(db.orders.find({"customer_id": user_id}).sort("created_at", -1))
    except Exception as e:
        print(f"Lỗi truy vấn: {e}")

    return render_template('dashboard.html', orders=orders, role=role)


# --- 3. TÍNH NĂNG ĐẶT ĐƠN HÀNG (MỚI) ---
@app.route('/order/create', methods=['GET', 'POST'])
def create_order():
    if 'user_id' not in session or session.get('role') != 'customer':
        flash("Bạn cần đăng nhập tài khoản khách hàng để đặt đơn!", "warning")
        return redirect(url_for('login_user'))

    if request.method == 'POST':
        item_name = request.form.get('item_name')
        weight = request.form.get('weight')
        pickup_address = request.form.get('pickup_address')
        delivery_address = request.form.get('delivery_address')

        region_id = session.get('region_id')
        db = get_db_by_region(region_id)

        # Tạo Node đơn hàng mới
        new_order = {
            "id": f"ORD{datetime.now().strftime('%H%M%S%f')[:8]}",
            "customer_id": session.get('user_id'),
            "item_name": item_name,
            "weight": float(weight) if weight else 0,
            "pickup_address": pickup_address,
            "destination": delivery_address,  # Dùng 'destination' để khớp với dashboard.html
            "status": "Chờ lấy hàng",
            "region_id": region_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        db.orders.insert_one(new_order)
        flash("Đặt đơn hàng thành công! Đơn hàng đã được thêm vào hàng đợi.", "success")
        return redirect(url_for('dashboard'))

    return render_template('create_order.html')


# --- 4. ĐĂNG NHẬP KHÁCH HÀNG ---
@app.route('/login', methods=['GET', 'POST'])
def login_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        for reg in ["North", "Central", "South"]:
            db = get_db_by_region(reg)
            user = db.users.find_one({"username": username, "password": password, "role": "customer"})
            if user:
                session.clear()
                session.update({
                    'user_id': user.get('user_id'),
                    'role': 'customer',
                    'region_id': reg,
                    'full_name': user.get('full_name')
                })
                return redirect(url_for('dashboard'))
        flash("Sai tài khoản hoặc mật khẩu khách hàng!", "error")
    return render_template('login_user.html')


# --- 5. ĐĂNG NHẬP NỘI BỘ (ADMIN/STAFF/SHIPPER) ---
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
        flash("Sai thông tin đăng nhập hoặc khu vực làm việc!", "error")
    return render_template('login_internal.html')


# --- 6. ĐĂNG KÝ TÀI KHOẢN (ĐÃ FIX BUG) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # FIX 1: Phải lấy đầy đủ dữ liệu từ Form trước
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        region = request.form.get('region')

        # Kiểm tra nếu người dùng bỏ trống trường nào đó
        if not all([username, password, full_name, region]):
            flash("Vui lòng điền đầy đủ thông tin!", "warning")
            return render_template('register.html')

        # FIX 2: Kiểm tra trùng tên trên TOÀN BỘ các Shard
        for reg in ["North", "Central", "South"]:
            db_check = get_db_by_region(reg)
            if db_check.users.find_one({"username": username}):
                flash(f"Tên đăng nhập '{username}' đã tồn tại hệ thống khu vực {reg}!", "warning")
                return render_template('register.html')

        # FIX 3: Tạo object user sau khi đã lấy đủ data
        new_user = {
            "user_id": f"CUST_{datetime.now().strftime('%H%M%S%f')[:10]}",
            "username": username,
            "password": password,
            "role": "customer",
            "full_name": full_name,
            "region_id": region,
            "created_at": datetime.now()
        }

        # FIX 4: Chỉ insert 1 lần vào đúng Shard đã chọn
        try:
            db = get_db_by_region(region)
            db.users.insert_one(new_user)
            flash("Đăng ký thành công! Mời bạn đăng nhập.", "success")
            return redirect(url_for('login_user'))
        except Exception as e:
            flash(f"Lỗi hệ thống khi lưu dữ liệu: {e}", "error")

    return render_template('register.html')
# --- 7. ĐĂNG XUẤT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)