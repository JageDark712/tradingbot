"""
Script de exploración: busca los nombres reales de símbolos en Exness
para oro, petróleo, gas natural e índices bursátiles.
"""
from mt5linux import MetaTrader5

mt5 = MetaTrader5()

if not mt5.initialize():
    print("ERROR: No se pudo conectar a MT5.")
    print("Verifica que el terminal MT5 esté abierto y logueado.")
    print("Último error:", mt5.last_error())
    exit()

print("Conexión exitosa.")
print("Cuenta:", mt5.account_info())

symbols = mt5.symbols_get()
nombres = [s.name for s in symbols]

print(f"\nTotal de símbolos disponibles: {len(nombres)}")

terminos_busqueda = ["XAU", "OIL", "GAS", "500", "100", "30", "DAX", "FTSE"]

for term in terminos_busqueda:
    print(f"\n--- Coincidencias con '{term}' ---")
    encontrados = [n for n in nombres if term in n.upper()]
    if encontrados:
        for n in encontrados:
            print(" ", n)
    else:
        print("  (sin resultados)")

mt5.shutdown()
