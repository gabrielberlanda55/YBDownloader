import os
import re
import boto3
import yt_dlp
from flask import Flask, render_template, request, jsonify, redirect
from dotenv import load_dotenv 

load_dotenv()

BUCKET_NAME =  os.getenv('BUCKET')
aws_acess_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

app = Flask(__name__)

# Configurações da AWS S3
s3 = boto3.client('s3', aws_access_key_id=aws_acess_key,
                  aws_secret_access_key=aws_secret_key)


def sanitize_filename(title):
    # Remove caracteres especiais para criar um nome de arquivo válido
    return re.sub(r'[\\/*?:"<>|]', "", title)

def get_temp_directory():
    # Verifica se uma variável de ambiente TEMP_DIR está configurada
    return os.getenv('TEMP_DIR', os.path.join(os.getcwd(), 'temp'))

def download_music_from_youtube(youtube_url):
    # Extrai informações do vídeo
    with yt_dlp.YoutubeDL() as ydl:
        info_dict = ydl.extract_info(youtube_url, download=False)
        title = info_dict.get('title', None)
        
        # Sanitiza o título para ser usado como nome de arquivo
        file_name = sanitize_filename(title)
    
    # Define o caminho para salvar o arquivo sem a extensão .mp3
    temp_dir = get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)  # Cria o diretório se ele não existir
    temp_file_path = os.path.join(temp_dir, f'{file_name}')  # Sem .mp3 aqui

    # Configurações para baixar o áudio em formato MP3
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{temp_file_path}.%(ext)s',  # yt-dlp adiciona a extensão correta
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    # Faz o download da música
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    
    # O caminho final do arquivo será com .mp3
    final_file_path = f'{temp_file_path}.mp3'

    # Verifica se o arquivo foi baixado
    if os.path.exists(final_file_path):
        print(f"Arquivo baixado: {final_file_path}")
        return final_file_path, file_name
    else:
        raise FileNotFoundError(f"O arquivo {final_file_path} não foi encontrado após o download.")

def upload_to_s3(file_path, s3_filename):
    # Faz upload do arquivo para o S3
    try:
        print(f"Enviando {file_path} para S3 com o nome {s3_filename}")
        s3.upload_file(file_path, BUCKET_NAME, s3_filename)
        s3_url = f'https://{BUCKET_NAME}.s3.amazonaws.com/{s3_filename}'
        print(f'Arquivo enviado para {s3_url}')
        return s3_url
    except Exception as e:
        print(f'Erro ao enviar para o S3: {e}')
        return None

def generate_download_link(bucket, s3_file, expiration=3600):
    try:
        url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': bucket, 
                                                'Key': s3_file,
                                                'ResponseContentDisposition': 'attachment'},
                                        ExpiresIn=expiration)
        return url
    except Exception as e:
        print(e)
        return None

def delete_local_file(file_path):
    # Remove o arquivo temporário do servidor
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f'Arquivo local {file_path} excluído.')
    else:
        print(f'O arquivo {file_path} não existe.')



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    try:
        temp_file_path, file_name = download_music_from_youtube(url)

        s3_url = upload_to_s3(temp_file_path, f'musicas/{file_name}.mp3')
        tempLinkdownload = generate_download_link(BUCKET_NAME,f'musicas/{file_name}.mp3',3600)
        print(tempLinkdownload)
        delete_local_file(temp_file_path)

        data = {
            "aws_url":tempLinkdownload
        }
        
        return data,200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='8000')