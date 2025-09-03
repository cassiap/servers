
# Explorer de Servidores (Streamlit) — v3
- Mapeado para cabeçalhos reais: **Equipe Responsável**, **Sistema/Serviço/Produto**, **Descrição do IC**, **Ambiente**, **Nome/Hostname**.
- Auto-carrega **qualquer .xlsx na pasta** (ex.: `FULL MIDD - 2025.xlsx`) se `servidores.xlsx` não existir.
- **Detalhes do servidor**: selecione um servidor filtrado e veja **todas as colunas** transpostas.

## Rodar
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```
Coloque seu Excel na mesma pasta (pode manter o nome original) ou envie pelo uploader.
