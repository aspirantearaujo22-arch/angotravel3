from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import json
import os
from datetime import datetime
import io
import base64

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessao_viagens_angola'

# Determinar o caminho absoluto do arquivo JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, 'launch.json')

# Carregar dados do JSON
def carregar_dados():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                conteudo = f.read().strip()
                if conteudo:
                    return json.loads(conteudo)
                else:
                    return {"usuarios": [], "viagens": [], "reservas": [], "configuracoes": {}}
        except json.JSONDecodeError:
            print("Arquivo JSON corrompido. Criando nova estrutura.")
            return {"usuarios": [], "viagens": [], "reservas": [], "configuracoes": {}}
    else:
        return {"usuarios": [], "viagens": [], "reservas": [], "configuracoes": {}}

# Salvar dados no JSON
def salvar_dados(dados):
    try:
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar dados: {e}")

# Gerar número de fatura
def gerar_numero_fatura():
    ano = datetime.now().strftime('%Y')
    mes = datetime.now().strftime('%m')
    dados = carregar_dados()
    num_faturas = len([r for r in dados.get('reservas', []) if 'fatura' in r])
    return f"FAT-{ano}{mes}-{num_faturas + 1:04d}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        dados = carregar_dados()
        
        novo_usuario = {
            'id': len(dados['usuarios']) + 1,
            'nome': request.form['nome'],
            'email': request.form['email'],
            'senha': request.form['senha'],
            'telefone': request.form.get('telefone', ''),
            'nif': request.form.get('nif', ''),
            'data_cadastro': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        dados['usuarios'].append(novo_usuario)
        salvar_dados(dados)
        
        return redirect(url_for('login'))
    
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        dados = carregar_dados()
        email = request.form['email']
        senha = request.form['senha']
        
        for usuario in dados['usuarios']:
            if usuario['email'] == email and usuario['senha'] == senha:
                session['usuario_id'] = usuario['id']
                session['usuario_nome'] = usuario['nome']
                return redirect(url_for('viagens'))
        
        return render_template('login.html', erro='Email ou senha inválidos')
    
    return render_template('login.html')

@app.route('/viagens')
def viagens():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    return render_template('viagens.html', viagens=dados['viagens'], usuario=session['usuario_nome'])

@app.route('/selecionar_viagem/<int:viagem_id>', methods=['POST'])
def selecionar_viagem(viagem_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    # Encontrar a viagem selecionada
    viagem_selecionada = None
    for viagem in dados['viagens']:
        if viagem['id'] == viagem_id:
            viagem_selecionada = viagem
            break
    
    if viagem_selecionada:
        # Buscar dados do usuário
        usuario = None
        for u in dados['usuarios']:
            if u['id'] == session['usuario_id']:
                usuario = u
                break
        
        # Gerar número da fatura
        numero_fatura = gerar_numero_fatura()
        
        # Criar reserva com dados de fatura
        nova_reserva = {
            'id': len(dados.get('reservas', [])) + 1,
            'usuario_id': session['usuario_id'],
            'usuario_nome': session['usuario_nome'],
            'usuario_nif': usuario.get('nif', 'Não informado'),
            'usuario_telefone': usuario.get('telefone', 'Não informado'),
            'viagem_id': viagem_id,
            'origem': viagem_selecionada['origem'],
            'destino': viagem_selecionada['destino'],
            'data': viagem_selecionada['data'],
            'horario_partida': viagem_selecionada['horario_partida'],
            'horario_chegada': viagem_selecionada['horario_chegada'],
            'preco': viagem_selecionada['preco'],
            'empresa': viagem_selecionada['empresa'],
            'data_reserva': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pendente_pagamento',
            'fatura': {
                'numero': numero_fatura,
                'data_emissao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_vencimento': (datetime.now().replace(hour=23, minute=59, second=59)).strftime('%Y-%m-%d 23:59:59'),
                'valor': viagem_selecionada['preco'],
                'estado': 'emitida',
                'metodo_pagamento': 'Transferência Bancária'
            }
        }
        
        if 'reservas' not in dados:
            dados['reservas'] = []
        
        dados['reservas'].append(nova_reserva)
        salvar_dados(dados)
        
        return redirect(url_for('detalhes_reserva', reserva_id=nova_reserva['id']))
    
    return redirect(url_for('viagens'))

@app.route('/detalhes_reserva/<int:reserva_id>')
def detalhes_reserva(reserva_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    # Encontrar a reserva
    reserva = None
    for r in dados.get('reservas', []):
        if r['id'] == reserva_id and r['usuario_id'] == session['usuario_id']:
            reserva = r
            break
    
    if not reserva:
        return redirect(url_for('minhas_reservas'))
    
    return render_template('detalhes_reserva.html', 
                         reserva=reserva, 
                         config=dados.get('configuracoes', {}),
                         usuario=session['usuario_nome'])

@app.route('/confirmar_pagamento/<int:reserva_id>', methods=['POST'])
def confirmar_pagamento(reserva_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    for reserva in dados['reservas']:
        if reserva['id'] == reserva_id and reserva['usuario_id'] == session['usuario_id']:
            reserva['status'] = 'confirmada'
            reserva['fatura']['estado'] = 'paga'
            reserva['fatura']['data_pagamento'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            salvar_dados(dados)
            break
    
    return redirect(url_for('minhas_reservas'))

@app.route('/minhas_reservas')
def minhas_reservas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    if 'reservas' not in dados:
        dados['reservas'] = []
    
    # Filtrar reservas do usuário atual
    reservas_usuario = []
    for reserva in dados['reservas']:
        if reserva['usuario_id'] == session['usuario_id']:
            reservas_usuario.append(reserva)
    
    return render_template('minhas_reservas.html', 
                         reservas=reservas_usuario, 
                         usuario=session['usuario_nome'])

@app.route('/fatura/<int:reserva_id>')
def ver_fatura(reserva_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    # Encontrar a reserva
    reserva = None
    for r in dados.get('reservas', []):
        if r['id'] == reserva_id and r['usuario_id'] == session['usuario_id']:
            reserva = r
            break
    
    if not reserva:
        return redirect(url_for('minhas_reservas'))
    
    return render_template('fatura.html', 
                         reserva=reserva, 
                         config=dados.get('configuracoes', {}),
                         usuario=session['usuario_nome'])

@app.route('/cancelar_reserva/<int:reserva_id>', methods=['POST'])
def cancelar_reserva(reserva_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    dados = carregar_dados()
    
    if 'reservas' in dados:
        for reserva in dados['reservas']:
            if reserva['id'] == reserva_id and reserva['usuario_id'] == session['usuario_id']:
                reserva['status'] = 'cancelada'
                reserva['fatura']['estado'] = 'cancelada'
                salvar_dados(dados)
                break
    
    return redirect(url_for('minhas_reservas'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/viagens')
def api_viagens():
    dados = carregar_dados()
    return jsonify(dados['viagens'])

if __name__ == '__main__':
    # Verificar se o arquivo launch.json existe e é válido na inicialização
    dados_iniciais = carregar_dados()
    if not dados_iniciais.get('viagens'):
        # Criar dados iniciais
        dados_iniciais['viagens'] = [
            {
                "id": 1,
                "origem": "Luanda",
                "destino": "Benguela",
                "data": "2024-12-15",
                "horario_partida": "08:00",
                "horario_chegada": "14:00",
                "preco": 8500,
                "empresa": "AngoTravel",
                "provincia_destino": "Benguela",
                "disponivel": True
            }
        ]
        dados_iniciais['configuracoes'] = {
            "empresa": {
                "nome": "AngolaTravel",
                "nif": "5417283940",
                "endereco": "Rua da Missão, 123 - Luanda, Angola",
                "telefone": "+244 923 456 789",
                "email": "contato@angolatravel.co.ao"
            },
            "banco": {
                "iban": "AO06 0040 0000 1234 5678 9012 3",
                "bic": "BICAAOLU",
                "banco": "Banco Angolano de Investimentos (BAI)"
            }
        }
        salvar_dados(dados_iniciais)
        print("Arquivo launch.json criado com dados iniciais!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)