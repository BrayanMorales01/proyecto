from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta


app = Flask(__name__)



@app.route("/")
def index():
    return "¡Hola, Render!"

if __name__ == "__main__":
    # Usar el puerto proporcionado por Render (o 5000 por defecto)
    port = int(os.environ.get("PORT", 18930))
    app.run(host="0.0.0.0", port=port)


app.secret_key = 'supersecretkey'

EMAIL_ADDRESS = 'paleanempresa@gmail.com'
EMAIL_PASSWORD = 'gfnvkqmezotzphxi'

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configuración de MySQL
app.config['MYSQL_HOST'] = 'junction.proxy.rlwy.net'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'JoRzuebqENEmDPwRQhVACtjZxfKwTgzp'
app.config['MYSQL_DB'] = 'railway'
app.config['MYSQL_PORT'] = 18930


mysql = MySQL(app)

# Página principal (Inventario)
def send_verification_code(email, code):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    msg['Subject'] = 'Código de Verificación'

    body = f'Tu código de verificación es {code}. Este código expirará en 10 minutos.'
    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, email, msg.as_string())

# Generar un código aleatorio de 6 dígitos
def generate_verification_code():
    return random.randint(100000, 999999)

# Página principal (Inventario)
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM productos")
    productos = cur.fetchall()
    return render_template('index.html', productos=productos)

# Registro de usuarios con verificación de código
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        direccion = request.form['direccion']
        password = generate_password_hash(request.form['password'])
        rol = 3  # Usuario común por defecto

        # Generar código de verificación
        code = generate_verification_code()
        send_verification_code(email, code)

        # Almacenar el código y los datos temporalmente
        session['verification_code'] = code
        session['registration_data'] = {
            'nombre': nombre,
            'email': email,
            'password': password,
            'direccion': direccion,
            'rol': rol
        }
        session['code_expiration'] = datetime.now() + timedelta(minutes=10)

        flash("Se ha enviado un código de verificación a tu correo", "info")
        return redirect(url_for('verify_code'))
    return render_template('register.html')

# Verificación del código
@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        code = request.form['code']

        if 'verification_code' in session and 'code_expiration' in session:
            if datetime.now().replace(tzinfo=None) > session['code_expiration'].replace(tzinfo=None):
                flash("El código ha expirado", "error")
                return redirect(url_for('register'))

            if int(code) == session['verification_code']:
                # Obtener datos de registro almacenados
                data = session['registration_data']
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO usuarios (nombre, email, password, direccion, rol) VALUES (%s, %s, %s, %s, %s)",
                            (data['nombre'], data['email'], data['password'], data['direccion'], data['rol']))
                mysql.connection.commit()

                # Limpiar la sesión
                session.pop('verification_code', None)
                session.pop('registration_data', None)
                session.pop('code_expiration', None)

                flash("Registro exitoso, por favor inicia sesión", "success")
                return redirect(url_for('login'))
            else:
                flash("Código incorrecto", "error")
        else:
            flash("No se ha encontrado un código de verificación válido", "error")
            return redirect(url_for('register'))
    return render_template('verify_code.html')

# Recuperación de contraseña
@app.route('/recover_password', methods=['GET', 'POST'])
def recover_password():
    if request.method == 'POST':
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s", [email])
        user = cur.fetchone()

        if user:
            # Generar código de verificación
            code = generate_verification_code()
            send_verification_code(email, code)

            # Almacenar el código temporalmente
            session['verification_code'] = code
            session['recover_email'] = email
            session['code_expiration'] = datetime.now() + timedelta(minutes=10)

            flash("Se ha enviado un código de verificación a tu correo", "info")
            return redirect(url_for('verify_code_password'))
        else:
            flash("No se encontró una cuenta con ese correo electrónico", "error")
    return render_template('recover_password.html')

# Verificación de código para recuperar contraseña
@app.route('/verify_code_password', methods=['GET', 'POST'])
def verify_code_password():
    if request.method == 'POST':
        code = request.form['code']

        if 'verification_code' in session and 'code_expiration' in session:
            if datetime.now().replace(tzinfo=None) > session['code_expiration'].replace(tzinfo=None):
                flash("El código ha expirado", "error")
                return redirect(url_for('recover_password'))

            if int(code) == session['verification_code']:
                return redirect(url_for('reset_password'))
            else:
                flash("Código incorrecto", "error")
        else:
            flash("No se ha encontrado un código de verificación válido", "error")
            return redirect(url_for('recover_password'))
    return render_template('verify_code_password.html')

# Restablecer la contraseña
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = generate_password_hash(request.form['password'])
        email = session.get('recover_email')

        cur = mysql.connection.cursor()
        cur.execute("UPDATE usuarios SET password = %s WHERE email = %s", (new_password, email))
        mysql.connection.commit()

        flash("Tu contraseña ha sido actualizada", "success")

        # Limpiar la sesión
        session.pop('verification_code', None)
        session.pop('recover_email', None)
        session.pop('code_expiration', None)

        return redirect(url_for('login'))
    return render_template('reset_password.html')

# Iniciar sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s", [email])
        user = cur.fetchone()
        if user and check_password_hash(user[3], password):  # user[3] es la contraseña
            session['user_id'] = user[0]
            session['rol'] = user[7]  # user[7] es el rol
            if user[7] == 1:
                return redirect(url_for('admin'))
            elif user[7] == 2:
                return redirect(url_for('repartidor'))
            else:
                return redirect(url_for('usuario'))
        else:
            flash("Usuario o contraseña incorrecta", "error")
    return render_template('login.html')


@app.route('/carrito-inicio')
def carrito_inicio():
    return render_template('login.html') 


@app.route('/politica-cookies')
def politica_cookies():
    return render_template('cookies.html')


# Registro de usuarios comunes


# Panel de administrador (gestión de inventario, ventas y usuarios)
@app.route('/admin')
def admin():
    if 'rol' in session and session['rol'] == 1:
        cur = mysql.connection.cursor()

        # Obtener productos
        cur.execute("SELECT * FROM productos")
        productos = cur.fetchall()

        # Obtener ventas
        cur.execute("SELECT SUM(total) FROM pedidos")
        total_ventas = cur.fetchone()[0]

        # Obtener usuarios y repartidores
        cur.execute("SELECT * FROM usuarios WHERE rol = 2")
        repartidores = cur.fetchall()

        cur.execute("SELECT * FROM usuarios WHERE rol = 3")
        usuarios = cur.fetchall()

        return render_template('admin.html', productos=productos, total_ventas=total_ventas, repartidores=repartidores, usuarios=usuarios)
    else:
        return redirect(url_for('login'))

# Agregar producto (Solo Administrador)
# Agregar producto (Solo Administrador)
@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'rol' in session and session['rol'] == 1:
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        cantidad = request.form['cantidad']
        
        # Manejo de la imagen
        if 'imagen' not in request.files or request.files['imagen'].filename == '':
            flash("No seleccionaste una imagen", "error")
            return redirect(request.url)
        
        file = request.files['imagen']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)  # Ruta completa para guardar el archivo
            file.save(file_path)
            imagen_url = f"uploads/{filename}"  # Ruta relativa que se almacenará en la base de datos
        else:
            flash("Formato de imagen no permitido", "error")
            return redirect(request.url)

        # Guardar el producto en la base de datos
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO productos (nombre, descripcion, precio, cantidad, imagen) VALUES (%s, %s, %s, %s, %s)",
                    (nombre, descripcion, precio, cantidad, imagen_url))
        mysql.connection.commit()
        flash("Producto añadido exitosamente", "success")
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('login'))


# Eliminar producto (Solo Administrador)
@app.route('/admin/delete_product/<int:id>')
def delete_product(id):
    if 'rol' in session and session['rol'] == 1:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM productos WHERE id = %s", [id])
        mysql.connection.commit()
        flash("Producto eliminado exitosamente", "success")
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('login'))

# Ver total de ventas
@app.route('/admin/ventas')
def ventas():
    if 'rol' in session and session['rol'] == 1:
        cur = mysql.connection.cursor()
        cur.execute("SELECT SUM(total) AS total_ventas FROM pedidos")
        total_ventas = cur.fetchone()[0]
        return render_template('ventas.html', total_ventas=total_ventas)
    else:
        return redirect(url_for('login'))

# Registrar repartidor (Solo Administrador)
@app.route('/admin/add_repartidor', methods=['POST'])
def add_repartidor():
    if 'rol' in session and session['rol'] == 1:
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        placa_vehiculo = request.form['placa_vehiculo']
        password = generate_password_hash(request.form['password'])
        rol = 2  # Rol de repartidor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (nombre, email, password, telefono, placa_vehiculo, rol) VALUES (%s, %s, %s, %s, %s, %s)",
                    (nombre, email, password, telefono, placa_vehiculo, rol))
        mysql.connection.commit()
        flash("Repartidor añadido exitosamente", "success")
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('login'))
    # Editar cantidad de producto (Solo Administrador)
@app.route('/admin/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'rol' in session and session['rol'] == 1:
        cur = mysql.connection.cursor()

        if request.method == 'POST':
            nueva_cantidad = request.form['cantidad']
            cur.execute("UPDATE productos SET cantidad = %s WHERE id = %s", (nueva_cantidad, id))
            mysql.connection.commit()
            flash("Cantidad de producto actualizada", "success")
            return redirect(url_for('admin'))

        # Obtener los detalles del producto actual
        cur.execute("SELECT * FROM productos WHERE id = %s", [id])
        producto = cur.fetchone()

        return render_template('editar_producto.html', producto=producto)
    else:
        return redirect(url_for('login'))


# Panel de repartidor (ver pedidos)
@app.route('/repartidor')
def repartidor():
    if 'rol' in session and session['rol'] == 2:
        cur = mysql.connection.cursor()

        # Ver pedidos pendientes y entregados
        cur.execute("SELECT * FROM pedidos WHERE estado = 'Pendiente'")
        pedidos_pendientes = cur.fetchall()

        cur.execute("SELECT * FROM pedidos WHERE estado = 'Entregado'")
        pedidos_entregados = cur.fetchall()

        return render_template('repartidor.html', pedidos_pendientes=pedidos_pendientes, pedidos_entregados=pedidos_entregados)
    else:
        return redirect(url_for('login'))

# Marcar pedido como entregado (Solo repartidor)
@app.route('/repartidor/entregar_pedido/<int:id>')
def entregar_pedido(id):
    if 'rol' in session and session['rol'] == 2:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE pedidos SET estado = 'Entregado' WHERE id = %s", [id])
        mysql.connection.commit()
        flash("Pedido marcado como entregado", "success")
        return redirect(url_for('repartidor'))
    else:
        return redirect(url_for('login'))

# Panel de usuario (ver productos, historial de pedidos, agregar al carrito)
# Panel de usuario (ver productos, historial de pedidos, agregar al carrito)
@app.route('/usuario')
def usuario():
    if 'rol' in session and session['rol'] == 3:
        cur = mysql.connection.cursor()
        
        # Obtener datos del usuario
        cur.execute("SELECT nombre, email, direccion FROM usuarios WHERE id = %s", [session['user_id']])
        datos_usuario = cur.fetchone()

        # Obtener productos
        cur.execute("SELECT * FROM productos")
        productos = cur.fetchall()
        
        # Obtener el carrito del usuario
        cur.execute("SELECT carrito.id_producto, carrito.cantidad, productos.precio, productos.nombre, productos.imagen FROM carrito JOIN productos ON carrito.id_producto = productos.id WHERE carrito.id_usuario = %s", [session['user_id']])
        carrito = cur.fetchall()

        # Obtener el historial de pedidos del usuario
        cur.execute("""
            SELECT pedidos.id, pedidos.total, pedidos.fecha, pedidos.estado
            FROM pedidos
            WHERE pedidos.id_usuario = %s
        """, [session['user_id']])
        historial_pedidos = cur.fetchall()

        total_carrito = sum(item[1] * item[2] for item in carrito)

        return render_template('usuario.html', 
                             productos=productos, 
                             carrito=carrito, 
                             historial_pedidos=historial_pedidos, 
                             total_carrito=total_carrito,
                             usuario=datos_usuario)
    else:
        return redirect(url_for('login'))

# Agregar al carrito (Solo usuario común)
@app.route('/usuario/agregar_carrito/<int:id>', methods=['POST'])
def agregar_carrito(id):
    if 'rol' in session and session['rol'] == 3:
        cantidad = int(request.form['cantidad'])
        user_id = session['user_id']
        
        # Crear cursor y verificar si el producto ya está en el carrito del usuario
        cur = mysql.connection.cursor()
        cur.execute("SELECT cantidad FROM carrito WHERE id_usuario = %s AND id_producto = %s", (user_id, id))
        producto_en_carrito = cur.fetchone()
        
        if producto_en_carrito:
            # Si el producto ya está en el carrito, se actualiza la cantidad
            nueva_cantidad = producto_en_carrito[0] + cantidad
            cur.execute("UPDATE carrito SET cantidad = %s WHERE id_usuario = %s AND id_producto = %s",
                        (nueva_cantidad, user_id, id))
        else:
            # Si el producto no está en el carrito, se inserta como nuevo
            cur.execute("INSERT INTO carrito (id_usuario, id_producto, cantidad) VALUES (%s, %s, %s)",
                        (user_id, id, cantidad))
        
        # Guardar los cambios en la base de datos
        mysql.connection.commit()
        flash("Producto añadido al carrito", "success")
        return redirect(url_for('usuario'))
    else:
        return redirect(url_for('login'))

    
# Realizar compra y generar factura (Solo usuario común)
# Realizar compra y generar factura (Solo usuario común)
@app.route('/usuario/realizar_compra', methods=['POST'])
def realizar_compra():
    if 'rol' in session and session['rol'] == 3:
        cur = mysql.connection.cursor()

        # Obtener los productos del carrito del usuario
        cur.execute("SELECT carrito.id_producto, carrito.cantidad, productos.precio, productos.cantidad FROM carrito JOIN productos ON carrito.id_producto = productos.id WHERE carrito.id_usuario = %s", [session['user_id']])
        carrito = cur.fetchall()

        if not carrito:
            flash("No tienes productos en el carrito", "error")
            return redirect(url_for('usuario'))

        total = 0
        for item in carrito:
            producto_id = item[0]
            cantidad_carrito = item[1]
            precio_producto = item[2]
            cantidad_disponible = item[3]
            
            # Verificar si hay suficiente cantidad en el inventario
            if cantidad_carrito > cantidad_disponible:
                flash(f"No hay suficiente stock para el producto con ID {producto_id}", "error")
                return redirect(url_for('usuario'))
            
            total += cantidad_carrito * precio_producto  # cantidad * precio

        # Insertar el pedido en la base de datos
        cur.execute("INSERT INTO pedidos (id_usuario, total, estado) VALUES (%s, %s, 'Pendiente')", (session['user_id'], total))
        pedido_id = cur.lastrowid

        # Restar la cantidad comprada del inventario
        for item in carrito:
            producto_id = item[0]
            cantidad_carrito = item[1]
            cantidad_disponible = item[3]
            
            # Restar la cantidad del producto
            nueva_cantidad = cantidad_disponible - cantidad_carrito
            cur.execute("UPDATE productos SET cantidad = %s WHERE id = %s", (nueva_cantidad, producto_id))
        
        # Vaciar el carrito del usuario
        cur.execute("DELETE FROM carrito WHERE id_usuario = %s", [session['user_id']])
        
        mysql.connection.commit()

        flash("Compra realizada con éxito", "success")
        return redirect(url_for('usuario'))
    else:
        return redirect(url_for('login'))


    # Ver historial de pedidos y facturas (Solo usuario común)

@app.route('/actualizar_direccion', methods=['POST'])
def actualizar_direccion():
    if 'user_id' in session:
        nueva_direccion = request.form['direccion']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE usuarios SET direccion = %s WHERE id = %s", 
                   (nueva_direccion, session['user_id']))
        mysql.connection.commit()
        flash("Dirección actualizada exitosamente", "success")
        return redirect(url_for('usuario'))
    return redirect(url_for('login'))

@app.route('/cerrar_sesion', endpoint='logout')
def logout():
    # Código para cerrar la sesión
    session.pop('user_id', None)
    return redirect(url_for('login'))
    

if __name__ == '__main__':
    app.run(debug=True)
    
