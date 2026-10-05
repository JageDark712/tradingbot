# Proyecto trading-scanner

Scanner multi-estrategia (trend following + momentum, con confluencia) que opera en Exness vía MT5/mt5linux sobre cuenta demo.
Capas: data/ -> indicators/ -> strategies/ -> confluence/ -> risk/ -> execution/ -> scanner/.

## Reglas de trabajo
- Después de cada cambio, agrega una entrada a CHANGELOG.md: fecha, archivos tocados y motivo.
- Si cambias la arquitectura o algún parámetro de riesgo, actualiza también README.md.
- Nunca leas, muestres ni subas el contenido de .env.
- Los parámetros están en config/settings.py; no los dejes fijos dentro del código.
- Cada cambio en un commit con mensaje claro.
