import sqlite3

def explorar_base_datos(archivo_db):
    """
    Función para explorar la estructura de una base de datos SQLite
    """
    try:
        # Conectar a la base de datos
        conexion = sqlite3.connect(archivo_db)
        cursor = conexion.cursor()
        
        print(f"🔍 Explorando base de datos: {archivo_db}\n")
        
        # 1. Obtener todas las tablas
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name;
        """)
        
        tablas = cursor.fetchall()
        
        if not tablas:
            print("❌ No se encontraron tablas en la base de datos")
            return
        
        print("📋 TABLAS ENCONTRADAS:")
        print("-" * 50)
        
        # 2. Para cada tabla, mostrar su estructura
        for tabla in tablas:
            nombre_tabla = tabla[0]
            
            # Obtener información de la tabla
            cursor.execute(f"PRAGMA table_info({nombre_tabla})")
            columnas = cursor.fetchall()
            
            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {nombre_tabla}")
            total_registros = cursor.fetchone()[0]
            
            print(f"\n📌 Tabla: {nombre_tabla}")
            print(f"   Registros: {total_registros}")
            print("   Columnas:")
            
            for columna in columnas:
                # columna: (id, nombre, tipo, notnull, default, pk)
                nombre_col = columna[1]
                tipo_col = columna[2]
                pk = "🔑 PK" if columna[5] else ""
                print(f"     - {nombre_col}: {tipo_col} {pk}")
            
            # Buscar tablas que podrían ser de reseñas
            if any(palabra in nombre_tabla.lower() for palabra in ['review', 'reseña', 'coment', 'rating', 'opinion']):
                print(f"   ⭐ POSIBLE TABLA DE RESEÑAS")
        
        # 3. Mostrar las primeras filas de tablas relevantes
        print("\n" + "="*50)
        print("🔍 BUSCANDO RESEÑAS...")
        print("="*50)
        
        for tabla in tablas:
            nombre_tabla = tabla[0]
            
            # Buscar tablas que podrían tener reseñas
            cursor.execute(f"PRAGMA table_info({nombre_tabla})")
            columnas = cursor.fetchall()
            nombres_columnas = [col[1].lower() for col in columnas]
            
            # Palabras clave que podrían indicar una tabla de reseñas
            palabras_clave = ['review', 'reseña', 'rating', 'comentario', 'opinion', 'calificacion']
            
            if any(palabra in nombre_tabla.lower() for palabra in palabras_clave) or \
               any(any(palabra in col for col in nombres_columnas) for palabra in palabras_clave):
                
                print(f"\n📊 Tabla: {nombre_tabla}")
                print("-" * 40)
                
                # Mostrar primeras 5 filas
                try:
                    cursor.execute(f"SELECT * FROM {nombre_tabla} LIMIT 5")
                    filas = cursor.fetchall()
                    
                    if filas:
                        # Mostrar nombres de columnas
                        headers = [col[1] for col in columnas]
                        print(" | ".join(headers))
                        print("-" * 60)
                        
                        # Mostrar datos
                        for fila in filas:
                            print(" | ".join(str(valor)[:20] for valor in fila))
                    else:
                        print("(Tabla vacía)")
                        
                except Exception as e:
                    print(f"Error al leer tabla: {e}")
        
        # 4. Consulta específica para contar reseñas
        print("\n" + "="*50)
        print("📊 CONSULTAS PARA CONTAR RESEÑAS")
        print("="*50)
        
        print("\nPuedes probar estas consultas:")
        print('1. cursor.execute("SELECT COUNT(*) FROM nombre_tabla")')
        print('2. cursor.execute("SELECT COUNT(*) FROM nombre_tabla WHERE rating IS NOT NULL")')
        print('3. cursor.execute("SELECT rating, COUNT(*) FROM nombre_tabla GROUP BY rating")')
        
        # Preguntar al usuario qué tabla quiere consultar
        while True:
            tabla_seleccionada = input("\n¿De qué tabla quieres contar las reseñas? (o 'salir' para terminar): ").strip()
            
            if tabla_seleccionada.lower() == 'salir':
                break
            
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla_seleccionada}")
                total = cursor.fetchone()[0]
                print(f"✅ Total de registros en {tabla_seleccionada}: {total}")
                
                # Si tiene columna de rating, mostrar distribución
                cursor.execute(f"PRAGMA table_info({tabla_seleccionada})")
                columnas = cursor.fetchall()
                if any('rating' in col[1].lower() for col in columnas):
                    cursor.execute(f"SELECT rating, COUNT(*) FROM {tabla_seleccionada} GROUP BY rating")
                    distribucion = cursor.fetchall()
                    if distribucion:
                        print("\n📊 Distribución por rating:")
                        for rating, count in distribucion:
                            print(f"  Rating {rating}: {count} reseñas")
                            
            except sqlite3.Error as e:
                print(f"❌ Error: {e}")
        
    except sqlite3.Error as e:
        print(f"❌ Error al conectar a la base de datos: {e}")
    finally:
        if conexion:
            conexion.close()
            print("\n✅ Conexión cerrada")

# Uso del script
if __name__ == "__main__":
    # Cambia esto por la ruta de tu base de datos
    archivo_db = "data/reviews.db"  # ← CAMBIA ESTO
    
    explorar_base_datos(archivo_db)