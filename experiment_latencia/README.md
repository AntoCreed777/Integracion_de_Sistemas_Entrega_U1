# Diseño experimental

## Objetivo

Evaluar el efecto del uso de **Redis como mecanismo de caché** sobre el rendimiento de una API REST al consultar un recurso solicitado frecuentemente, comparando escenarios con y sin caché bajo condiciones controladas.

## Hipótesis

**Hipótesis nula (\(H_0\))**

El uso de Redis no produce una diferencia estadísticamente significativa en el tiempo de respuesta:

$$
H_0:\mu_{\text{cache}}=\mu_{\text{sin cache}}
$$

**Hipótesis alternativa (\(H_1\))**

El uso de Redis reduce el tiempo de respuesta:

$$
H_1:\mu_{\text{cache}}<\mu_{\text{sin cache}}
$$

## Variables

### Variable independiente

Uso de Redis como mecanismo de caché:

| Condición    | Redis         |
| ------------ | ------------- |
| Control      | Deshabilitado |
| Experimental | Habilitado    |

Cuando Redis esté habilitado, se evaluarán tres patrones: **HIT, MISS y HIT/MISS (50/50)**.

### Variable dependiente

**Tiempo de respuesta de la API**, medido en milisegundos desde el envío de la solicitud hasta la recepción de la respuesta.

### Variables controladas

Se mantendrán constantes la API, consulta, datos, infraestructura, base de datos, configuración de Redis, carga generada y condiciones de ejecución.

## Escenarios experimentales

| Escenario          | Configuración       | Comportamiento                                           |
| ------------------ | ------------------- | -------------------------------------------------------- |
| **A — Sin caché**  | Redis deshabilitado | Todas las solicitudes consultan la BD.                   |
| **B — Cache HIT**  | Redis habilitado    | Las solicitudes obtienen los datos desde Redis.          |
| **C — Cache MISS** | Redis habilitado    | Las solicitudes no encuentran el dato y consultan la BD. |
| **D — HIT/MISS**   | Redis habilitado    | 50 % de solicitudes HIT y 50 % MISS.                     |

En los escenarios con **MISS**, los datos obtenidos desde la BD serán almacenados en Redis según el comportamiento normal de la aplicación.

## Configuración de carga y repeticiones

Para garantizar una comparación controlada, se utilizará la misma carga en todos los escenarios:

* **Workers asíncronos:** 10.
* **Solicitudes por ejecución:** 1.000.
* **Repeticiones por escenario:** 5.

Antes de cada ejecución se realizará un **periodo de calentamiento (warm-up)** para evitar que la inicialización de la aplicación, conexiones o cachés afecte las mediciones.

La carga será generada de manera concurrente mediante los 10 workers, manteniendo la misma configuración para todos los escenarios.

## Métricas

Se medirán las siguientes métricas:

### Tiempo de respuesta

Se calcularán:

* Media.
* Desviación estándar.
* P1.
* P5.
* P25.
* P50 (mediana).
* P75.
* P95.
* P99.

Esto permitirá analizar tanto el comportamiento central como la variabilidad y las latencias altas.

### Throughput

Se medirá el **throughput o Requests Per Second (RPS)**:

$$
RPS=\frac{N}{T}
$$

donde \(N\) corresponde al número de solicitudes procesadas y \(T\) al tiempo total empleado en segundos.

### Acceso a la base de datos

Se registrará la cantidad de solicitudes que requieren acceso a la base de datos, permitiendo comparar la reducción de carga producida por Redis.

Para los escenarios con caché también se registrará la cantidad y proporción de **HIT** y **MISS**:

$$
HitRate=\frac{HIT}{HIT+MISS}\times100
$$

## Análisis estadístico

Los resultados de los escenarios serán comparados mediante sus distribuciones de tiempo de respuesta. Se evaluará si la diferencia entre **caché habilitada y caché deshabilitada** es estadísticamente significativa, utilizando un nivel de significancia de:

$$
\alpha=0.05
$$

Además del valor \(p\), se considerará el tamaño de la diferencia observada para determinar la magnitud del efecto producido por Redis.
