import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import ast

# 1. Cargar el archivo CSV (cambia 'tu_archivo.csv' por el nombre real de tu archivo)
df = pd.read_csv('C:\\Users\\franj\\Desktop\\U\\Capstone\\Repo\\Capbot-test\\Testing\\Host\\capbot_20260428_222724.csv')

# 2. Convertir el texto de la columna 'imu' en diccionarios reales
# ast.literal_eval es una forma segura de evaluar strings que contienen estructuras de Python
df['imu'] = df['imu'].apply(ast.literal_eval)

# 3. Expandir el diccionario en múltiples columnas
# Esto creará una columna para mx, my, mz, ax, ay, az, gx, gy, gz
df_imu = pd.json_normalize(df['imu'])

# 4. Configurar el estilo del gráfico
sns.set_theme(style="whitegrid")
plt.figure(figsize=(12, 6))

# 5. Definir qué variables queremos graficar (puedes agregar 'ax', 'ay', 'az' si lo deseas)
variables = ['x', 'y']

# 6. Graficar la distribución (KDE) para cada variable
for var in variables:
    sns.kdeplot(data=df_imu, x=var, fill=True, alpha=0.5, label=var)

# 7. Detalles del gráfico
plt.title('Distribución de Probabilidades de Magnetómetro (mx, my, mz)', fontsize=14, pad=15)
plt.xlabel('muT', fontsize=12)
plt.ylabel('Densidad de Probabilidad', fontsize=12)
plt.legend(title='Ejes')
plt.tight_layout()

# Mostrar el gráfico
plt.show()