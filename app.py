import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Clase, AsistenciaClase, Producto, Venta
from datetime import datetime, date, timedelta
from sqlalchemy import func

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'boxfit_secret_key_2024')

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ====================== DASHBOARD ======================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    hoy = date.today()
    
    # Estadísticas
    total_alumnos = Alumno.query.filter_by(activo=True).count()
    alumnos_morosos = Alumno.query.filter_by(morosidad=True, activo=True).count()
    alumnos_vencidos = Alumno.query.filter(
        Alumno.activo == True,
        Alumno.fecha_baja == None,
        Alumno.ultimo_pago < hoy - timedelta(days=30)
    ).count()
    
    # Próximos vencimientos (alerta)
    alumnos_alerta = Alumno.query.filter(
        Alumno.activo == True,
        Alumno.ultimo_pago < hoy - timedelta(days=25),
        Alumno.ultimo_pago >= hoy - timedelta(days=30),
        Alumno.morosidad == False
    ).count()
    
    # Asistencias hoy
    asistencias_hoy = AsistenciaClase.query.filter_by(fecha=hoy).count()
    
    # Clases de hoy
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dia_actual = dias_semana[hoy.weekday()]
    clases_hoy = Clase.query.filter_by(dia=dia_actual).all()
    
    # Últimos alumnos
    ultimos_alumnos = Alumno.query.order_by(Alumno.id.desc()).limit(5).all()
    
    # Productos para venta rápida
    productos = Producto.query.filter(Producto.stock > 0).limit(10).all()
    
    stats = {
        'total_alumnos': total_alumnos,
        'alumnos_morosos': alumnos_morosos,
        'alumnos_vencidos': alumnos_vencidos,
        'alumnos_alerta': alumnos_alerta,
        'asistencias_hoy': asistencias_hoy,
        'clases_hoy': clases_hoy,
        'ultimos_alumnos': ultimos_alumnos,
        'productos': productos
    }
    
    return render_template('dashboard.html', stats=stats, now=datetime.now())

# ====================== LOGIN ======================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Bienvenido {user.username}', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# ====================== ALUMNOS ======================

@app.route('/alumnos')
@login_required
def alumnos():
    alumnos_lista = Alumno.query.order_by(Alumno.nombre).all()
    return render_template('alumnos.html', alumnos=alumnos_lista)

@app.route('/alumnos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    if request.method == 'POST':
        try:
            fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d').date() if request.form.get('fecha_inicio') else date.today()
            ultimo_pago = datetime.strptime(request.form['ultimo_pago'], '%Y-%m-%d').date() if request.form.get('ultimo_pago') else fecha_inicio
            
            nuevo = Alumno(
                nombre=request.form['nombre'],
                dni=request.form['dni'],
                telefono=request.form.get('telefono', ''),
                contacto_emergencia=request.form.get('contacto_emergencia', ''),
                telefono_emergencia=request.form.get('telefono_emergencia', ''),
                fecha_inicio=fecha_inicio,
                tipo_clase=request.form.get('tipo_clase'),
                valor_cuota=float(request.form.get('valor_cuota', 15000)),
                forma_pago=request.form.get('forma_pago'),
                clases_totales=int(request.form.get('clases_totales', 0)),
                clases_restantes=int(request.form.get('clases_totales', 0)),
                ultimo_pago=ultimo_pago,
                activo=True
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(f'Alumno {nuevo.nombre} agregado', 'success')
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('nuevo_alumno.html')

@app.route('/alumnos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            alumno.nombre = request.form['nombre']
            alumno.dni = request.form['dni']
            alumno.telefono = request.form.get('telefono', '')
            alumno.contacto_emergencia = request.form.get('contacto_emergencia', '')
            alumno.telefono_emergencia = request.form.get('telefono_emergencia', '')
            alumno.tipo_clase = request.form.get('tipo_clase')
            alumno.valor_cuota = float(request.form.get('valor_cuota', 15000))
            alumno.forma_pago = request.form.get('forma_pago')
            alumno.clases_totales = int(request.form.get('clases_totales', 0))
            alumno.notas = request.form.get('notas', '')
            
            # Si es baja
            if 'dar_baja' in request.form:
                alumno.activo = False
                alumno.fecha_baja = date.today()
                alumno.motivo_baja = request.form.get('motivo_baja', '')
                flash('Alumno dado de baja', 'warning')
            else:
                alumno.activo = 'activo' in request.form
                flash('Alumno actualizado', 'success')
            
            db.session.commit()
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('editar_alumno.html', alumno=alumno)

@app.route('/alumnos/registrar_pago/<int:id>', methods=['POST'])
@login_required
def registrar_pago(id):
    alumno = Alumno.query.get_or_404(id)
    monto = float(request.form.get('monto', 0))
    
    alumno.ultimo_pago = date.today()
    alumno.deuda = False
    alumno.morosidad = False
    db.session.commit()
    
    flash(f'Pago registrado para {alumno.nombre}. Próximo vencimiento en 30 días', 'success')
    return redirect(url_for('alumnos'))

@app.route('/alumnos/enviar_recordatorio/<int:id>')
@login_required
def enviar_recordatorio(id):
    alumno = Alumno.query.get_or_404(id)
    if alumno.telefono:
        mensaje = f"Hola {alumno.nombre}, te recordamos que tu cuota de BoxFit Gym vence en los próximos días. ¡No te atrases! 🥊"
        return redirect(f"https://wa.me/{alumno.telefono}?text={mensaje.replace(' ', '%20')}")
    flash('El alumno no tiene número registrado', 'error')
    return redirect(url_for('alumnos'))

@app.route('/alumnos/eliminar/<int:id>')
@login_required
def eliminar_alumno(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('alumnos'))
    
    alumno = Alumno.query.get_or_404(id)
    db.session.delete(alumno)
    db.session.commit()
    flash('Alumno eliminado', 'success')
    return redirect(url_for('alumnos'))

# ====================== ASISTENCIA ======================

@app.route('/asistencia/registrar', methods=['POST'])
@login_required
def registrar_asistencia():
    alumno_id = request.form.get('alumno_id')
    clase_id = request.form.get('clase_id')
    
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        flash('Alumno no encontrado', 'error')
        return redirect(url_for('clases'))
    
    # Verificar si ya asistió hoy
    ya_asistio = AsistenciaClase.query.filter_by(
        alumno_id=alumno_id,
        fecha=date.today()
    ).first()
    
    if ya_asistio:
        flash(f'{alumno.nombre} ya registró asistencia hoy', 'warning')
    else:
        nueva_asistencia = AsistenciaClase(
            alumno_id=alumno_id,
            clase_id=clase_id,
            fecha=date.today()
        )
        alumno.asistencia += 1
        if alumno.clases_restantes > 0:
            alumno.clases_restantes -= 1
        db.session.add(nueva_asistencia)
        db.session.commit()
        flash(f'✅ Asistencia registrada: {alumno.nombre}', 'success')
    
    return redirect(url_for('clases'))

# ====================== CLASES ======================

@app.route('/clases')
@login_required
def clases():
    clases_lista = Clase.query.order_by(Clase.dia, Clase.hora).all()
    alumnos_activos = Alumno.query.filter_by(activo=True).all()
    
    # Contar asistentes por clase hoy
    for clase in clases_lista:
        clase.asistentes_hoy = AsistenciaClase.query.filter_by(
            clase_id=clase.id,
            fecha=date.today()
        ).count()
    
    return render_template('clases.html', clases=clases_lista, alumnos_activos=alumnos_activos)

@app.route('/clases/nueva', methods=['POST'])
@login_required
def nueva_clase():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('clases'))
    
    try:
        nueva = Clase(
            nombre=request.form['nombre'],
            dia=request.form['dia'],
            hora=request.form['hora'],
            capacidad=int(request.form.get('capacidad', 20))
        )
        db.session.add(nueva)
        db.session.commit()
        flash('Clase creada', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('clases'))

@app.route('/clases/eliminar/<int:id>')
@login_required
def eliminar_clase(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('clases'))
    
    clase = Clase.query.get_or_404(id)
    db.session.delete(clase)
    db.session.commit()
    flash('Clase eliminada', 'success')
    return redirect(url_for('clases'))

# ====================== VENTAS ======================

@app.route('/ventas')
@login_required
def ventas():
    if current_user.role != 'admin':
        flash('Solo administradores pueden ver ventas', 'error')
        return redirect(url_for('index'))
    
    productos = Producto.query.all()
    ventas_lista = Venta.query.order_by(Venta.fecha.desc()).limit(100).all()
    return render_template('ventas.html', productos=productos, ventas=ventas_lista)

@app.route('/venta-rapida', methods=['POST'])
@login_required
def venta_rapida():
    try:
        producto_id = request.form.get('producto_id')
        cantidad = int(request.form.get('cantidad', 1))
        
        producto = Producto.query.get(producto_id)
        if not producto:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('index'))
        
        if producto.stock < cantidad:
            flash(f'Stock insuficiente', 'error')
            return redirect(url_for('index'))
        
        monto = producto.precio * cantidad
        
        venta = Venta(
            producto_id=producto.id,
            producto_nombre=producto.nombre,
            cantidad=cantidad,
            monto=monto,
            usuario_id=current_user.id
        )
        
        producto.stock -= cantidad
        db.session.add(venta)
        db.session.commit()
        
        flash(f'Venta registrada: {producto.nombre} x{cantidad} - ${monto}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/productos/nuevo', methods=['POST'])
@login_required
def nuevo_producto():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('ventas'))
    
    try:
        nuevo = Producto(
            nombre=request.form['nombre'],
            precio=float(request.form['precio']),
            stock=int(request.form.get('stock', 0))
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Producto agregado', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('ventas'))

# ====================== USUARIOS ======================

@app.route('/usuarios')
@login_required
def usuarios():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    usuarios_lista = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios_lista)

@app.route('/usuarios/nuevo', methods=['POST'])
@login_required
def nuevo_usuario():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    try:
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'operador')
        
        if User.query.filter_by(username=username).first():
            flash('Usuario ya existe', 'error')
            return redirect(url_for('usuarios'))
        
        nuevo = User(
            username=username,
            password=generate_password_hash(password),
            role=role
        )
        db.session.add(nuevo)
        db.session.commit()
        flash(f'Usuario {username} creado', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('usuarios'))

@app.route('/usuarios/reset_password/<int:id>')
@login_required
def reset_password(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    usuario = User.query.get_or_404(id)
    nueva_password = '123456'
    usuario.password = generate_password_hash(nueva_password)
    db.session.commit()
    flash(f'Contraseña de {usuario.username} restablecida a: {nueva_password}', 'success')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    if id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'error')
        return redirect(url_for('usuarios'))
    
    usuario = User.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado', 'success')
    return redirect(url_for('usuarios'))

# ====================== INICIALIZACIÓN ======================

@app.cli.command("init-db")
def init_db():
    db.create_all()
    
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> Usuario admin creado: admin / admin123")
    
    if not User.query.filter_by(username='operador').first():
        operador = User(username='operador', password=generate_password_hash('operador123'), role='operador')
        db.session.add(operador)
        db.session.commit()
        print(">>> Usuario operador creado: operador / operador123")
    
    if Producto.query.count() == 0:
        productos = [
            Producto(nombre='Agua', precio=800, stock=50),
            Producto(nombre='Isotónico', precio=1200, stock=30),
            Producto(nombre='Proteína', precio=2500, stock=20),
            Producto(nombre='Vendas', precio=3500, stock=40),
        ]
        for p in productos:
            db.session.add(p)
        db.session.commit()
        print(">>> Productos creados")
    
    if Clase.query.count() == 0:
        clases = [
            Clase(nombre='Boxeo', dia='Lunes', hora='18:00', capacidad=20),
            Clase(nombre='Boxeo', dia='Miércoles', hora='18:00', capacidad=20),
            Clase(nombre='Boxeo', dia='Viernes', hora='18:00', capacidad=20),
            Clase(nombre='Funcional', dia='Martes', hora='19:00', capacidad=15),
            Clase(nombre='Funcional', dia='Jueves', hora='19:00', capacidad=15),
        ]
        for c in clases:
            db.session.add(c)
        db.session.commit()
        print(">>> Clases creadas")
    
    print(">>> Base de datos inicializada")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)