import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'chave_super_secreta_do_bolao'

def iniciar_banco():
    conexao = sqlite3.connect('bolao.db')
    cursor = conexao.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            senha TEXT,
            pontos INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS palpites_oficiais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            time_a TEXT,
            gols_a INTEGER,
            time_b TEXT,
            gols_b INTEGER,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados_oficiais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time_a TEXT,
            gols_a INTEGER,
            gols_b INTEGER,
            time_b TEXT
        )
    ''')
    conexao.commit()
    conexao.close()

iniciar_banco()

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = ""
    if request.method == 'POST':
        acao = request.form.get('acao')
        nome = request.form.get('nome')
        senha = request.form.get('senha')
        
        conexao = sqlite3.connect('bolao.db')
        cursor = conexao.cursor()
        
        if acao == 'entrar':
            cursor.execute('SELECT * FROM usuarios WHERE nome=? AND senha=?', (nome, senha))
            usuario = cursor.fetchone()
            if usuario:
                session['usuario'] = nome
                return redirect(url_for('principal'))
            else:
                erro = "Nome ou senha incorretos!"
                
        elif acao == 'cadastrar':
            try:
                cursor.execute('INSERT INTO usuarios (nome, senha, pontos) VALUES (?, ?, 0)', (nome, senha))
                conexao.commit()
                session['usuario'] = nome
                return redirect(url_for('principal'))
            except:
                erro = "Este nome já existe! Escolha outro."
                
        conexao.close()
    return render_template('login.html', erro=erro)

@app.route('/sair')
def sair():
    session.pop('usuario', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def principal():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conexao = sqlite3.connect('bolao.db')
    cursor = conexao.cursor()
    
    if request.method == 'POST':
        if 'acao' in request.form and request.form['acao'] == 'novo_palpite':
            nome = session['usuario']
            time_a = request.form.get('time_a')
            gols_a = request.form.get('gols_time_a')
            gols_b = request.form.get('gols_time_b')
            time_b = request.form.get('time_b')
            
            cursor.execute('INSERT INTO palpites_oficiais (nome, time_a, gols_a, time_b, gols_b) VALUES (?, ?, ?, ?, ?)', 
                           (nome, time_a, gols_a, time_b, gols_b))
            conexao.commit()

    cursor.execute('SELECT nome, pontos FROM usuarios ORDER BY pontos DESC')
    ranking = cursor.fetchall()
    
    cursor.execute('SELECT nome, time_a, gols_a, gols_b, time_b, status FROM palpites_oficiais ORDER BY id DESC')
    dados_banco = cursor.fetchall()
    
    cursor.execute('SELECT time_a, gols_a, gols_b, time_b FROM resultados_oficiais ORDER BY id DESC')
    resultados = cursor.fetchall()
    conexao.close()
    
    return render_template('index.html', ranking=ranking, palpites=dados_banco, resultados=resultados, usuario_logado=session['usuario'])

# --- PÁGINA DO ADMIN COM SENHA ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    mensagem = ""
    erro = ""
    
    # 1. Verifica login e logout do Administrador
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'login_admin':
            senha = request.form.get('senha_admin')
            if senha == 'mestre123': # <-- SUA SENHA DO ADMIN AQUI
                session['admin_logado'] = True
            else:
                erro = "Senha de administrador incorreta!"
                
        elif acao == 'logout_admin':
            session.pop('admin_logado', None)
            
    # 2. Se o Admin NÃO estiver logado, para por aqui e mostra só a tela de senha
    if not session.get('admin_logado'):
        return render_template('admin.html', admin_logado=False, erro=erro)

    # 3. Se estiver logado, roda a lógica do painel normalmente
    conexao = sqlite3.connect('bolao.db')
    cursor = conexao.cursor()
    
    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'excluir_usuario':
            nome_usuario = request.form.get('nome_usuario')
            cursor.execute('DELETE FROM usuarios WHERE nome = ?', (nome_usuario,))
            cursor.execute('DELETE FROM palpites_oficiais WHERE nome = ?', (nome_usuario,))
            conexao.commit()
            mensagem = f"Usuário '{nome_usuario}' e seus palpites foram excluídos!"
            
        elif acao == 'lancar_resultado':
            time_a = request.form.get('time_a')
            gols_a_real = int(request.form.get('gols_a_real'))
            gols_b_real = int(request.form.get('gols_b_real'))
            time_b = request.form.get('time_b')
            
            cursor.execute('INSERT INTO resultados_oficiais (time_a, gols_a, gols_b, time_b) VALUES (?, ?, ?, ?)', 
                           (time_a, gols_a_real, gols_b_real, time_b))
            
            cursor.execute('SELECT id, nome, gols_a, gols_b FROM palpites_oficiais WHERE time_a=? AND time_b=? AND status="Pendente"', (time_a, time_b))
            palpites = cursor.fetchall()
            
            for palpite in palpites:
                id_palpite = palpite[0]
                nome = palpite[1]
                gols_a_palpite = palpite[2]
                gols_b_palpite = palpite[3]
                
                pontos_ganhos = 0
                saldo_real = gols_a_real - gols_b_real
                saldo_palpite = gols_a_palpite - gols_b_palpite
                
                if gols_a_palpite == gols_a_real and gols_b_palpite == gols_b_real:
                    pontos_ganhos = 5
                elif saldo_real == saldo_palpite:
                    pontos_ganhos = 3
                elif (saldo_real > 0 and saldo_palpite > 0) or (saldo_real < 0 and saldo_palpite < 0):
                    pontos_ganhos = 1
                        
                cursor.execute('UPDATE usuarios SET pontos = pontos + ? WHERE nome = ?', (pontos_ganhos, nome))
                cursor.execute('UPDATE palpites_oficiais SET status = ? WHERE id = ?', (f"+{pontos_ganhos} pts", id_palpite))
                
            conexao.commit()
            mensagem = f"Resultado salvo! Pontos de {len(palpites)} palpite(s) foram calculados."

    cursor.execute('SELECT nome FROM usuarios ORDER BY nome')
    lista_usuarios = cursor.fetchall()
    conexao.close()
    
    return render_template('admin.html', admin_logado=True, mensagem=mensagem, usuarios=lista_usuarios)

if __name__ == '__main__':
    app.run(debug=True)