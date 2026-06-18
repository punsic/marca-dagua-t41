import os
import io
import hashlib
from datetime import datetime
from flask import Flask, request, render_template, send_file, jsonify

from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4

# Tenta importar pypdf ou PyPDF2 para máxima compatibilidade
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        raise ImportError("Nenhuma biblioteca de PDF encontrada. Instale pypdf ou PyPDF2.")

app = Flask(__name__)

# Configura limite máximo de upload (ex: 32MB)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

def create_watermark_in_memory(buyer_name, buyer_doc):
    if buyer_doc and buyer_doc.lower() == "none":
        buyer_doc = ""
        
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # 1. CAMADA ESTEGANOGRÁFICA (Marca d'água quase invisível no fundo)
    c.saveState()
    c.setFillColor(Color(253/255.0, 253/255.0, 253/255.0, alpha=1.0))
    c.setFont("Helvetica-Bold", 14)
    words = buyer_name.upper().split()
    if len(words) > 2:
        mid = (len(words) + 1) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [buyer_name.upper()]
    
    for x in range(-200, int(width) + 200, 150):
        for y in range(-200, int(height) + 200, 150):
            c.saveState()
            c.translate(x, y)
            c.rotate(30)
            for i, line in enumerate(lines):
                c.drawString(0, -i * 14, line) 
            c.restoreState()
    c.restoreState()

    # 2. CAMADA VISÍVEL (Fica na frente, mas translúcida)
    c.saveState()
    c.setFillColor(Color(0.75, 0.75, 0.75, alpha=0.10))
    c.translate(width / 2, height / 2)
    c.rotate(45)
    
    c.setFont("Helvetica-Bold", 45)
    c.drawCentredString(0, 0, f"{buyer_name.upper()}")
    
    c.setFont("Helvetica", 25)
    c.drawCentredString(0, -40, "LICENÇA DE USO PESSOAL E INTRANSFERÍVEL")
    
    if buyer_doc:
        c.setFont("Helvetica", 20)
        c.drawCentredString(0, -70, f"ID: {buyer_doc}")
    c.restoreState()

    # 3. CAMADA INVISÍVEL (Metadados esteganográficos no texto da página)
    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.01))
    c.setFont("Helvetica", 1) 
    
    tx_hash = hashlib.md5(f"{buyer_name}{buyer_doc}{datetime.now()}".encode()).hexdigest()
    hidden_text = f"TRACKING_ID=[{tx_hash}] LICENSED_TO=[{buyer_name}] DOC=[{buyer_doc}]"
    
    c.drawString(5, 5, hidden_text)
    c.drawString(width - 150, 5, hidden_text)
    c.drawString(5, height - 5, hidden_text)
    c.drawString(width - 150, height - 5, hidden_text)
    
    for x in range(0, int(width), 100):
        for y in range(0, int(height), 100):
            c.drawString(x, y, hidden_text)
            
    c.restoreState()
    c.save()
    
    pdf_buffer.seek(0)
    return pdf_buffer, tx_hash

def process_pdf(input_stream, buyer_name, buyer_doc=""):
    # Cria a marca d'água em memória
    wm_stream, tx_hash = create_watermark_in_memory(buyer_name, buyer_doc)
    
    reader_main = PdfReader(input_stream)
    reader_wm = PdfReader(wm_stream)
    wm_page = reader_wm.pages[0]
    
    writer = PdfWriter()
    
    # Processa cada página aplicando a marca d'água SOBRE os elementos (para não ficar escondida por fundos sólidos)
    for page in reader_main.pages:
        # Mescla wm_page (marca d'água translúcida) por CIMA de page (conteúdo original)
        page.merge_page(wm_page)
        writer.add_page(page)
        
    # Copia e enriquece metadados para segurança extra
    metadata = reader_main.metadata
    new_metadata = {
        "/Author": "João Eduardo Santos Versiani & João Vitor Nunes",
        "/Creator": "Sistema Anti-Pirataria T41 Web",
        "/Subject": f"Licença de uso exclusivo concedida a {buyer_name}",
        "/Keywords": f"Licenciado, {buyer_name}, {buyer_doc}, {tx_hash}, Protegido",
        "/LicensedTo": buyer_name,
        "/TransactionHash": tx_hash 
    }
    
    if metadata:
        for key in metadata:
            if key not in new_metadata:
                new_metadata[key] = metadata[key]
                
    writer.add_metadata(new_metadata)
    
    output_stream = io.BytesIO()
    writer.write(output_stream)
    output_stream.seek(0)
    
    return output_stream, tx_hash

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/watermark', methods=['POST'])
def api_watermark():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
    file = request.files['file']
    buyer_name = request.form.get('name', '').strip()
    buyer_doc = request.form.get('doc', '').strip()
    
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400
        
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "O arquivo enviado deve ser um PDF"}), 400
        
    if not buyer_name:
        return jsonify({"error": "O nome do comprador é obrigatório"}), 400
        
    try:
        # Processa tudo em memória
        input_stream = io.BytesIO(file.read())
        output_stream, tx_hash = process_pdf(input_stream, buyer_name, buyer_doc)
        
        # Gera o nome do arquivo licenciado
        base_name, ext = os.path.splitext(file.filename)
        safe_name = "".join([c if c.isalnum() else "_" for c in buyer_name]).strip("_")
        output_filename = f"{base_name}_[Licenciado_{safe_name}]{ext}"
        
        return send_file(
            output_stream,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )
    except Exception as e:
        return jsonify({"error": f"Erro ao processar o PDF: {str(e)}"}), 500

if __name__ == '__main__':
    # Roda em 0.0.0.0 na porta 5000 para acesso via rede local
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
