🚀 AstraToons

Site de mangás e manhwas desenvolvida com foco em performance, organização e facilidade de uso.

---

## 📦 Sobre o Projeto

O **AstraToons** é uma plataforma voltada para a publicação de mangás e manhwas.  
💡 A intenção é ser um site inicial para as scans novas.

---

## 🔧 Instalação e Uso

Siga os passos abaixo para clonar e rodar o projeto localmente.

1) Clone o repositório  
`git clone https://github.com/StalkeRz2/astratoons.git`  
`cd astratoons`

2) Crie o ambiente virtual  
`C:\Users\seu usuario\AppData\Local\Programs\Python\Python311\python.exe -m venv venv`  
(Lembrando: usar Python 3.11)

3) Ative o ambiente virtual  
`.\venv\Scripts\Activate.ps1`

4) Instale as dependências  
`python -m pip install -r requirements.txt`

5) Verifique o projeto  
`cd astratoons`  
`python manage.py check`  
(⚠️ Se der erro no banco de dados, será necessário criar um novo)

6) Crie o superusuário  
`python manage.py createsuperuser`

7) Rode o servidor  
`python manage.py runserver`

---

## 🛠️ Se der erro no banco de dados:

1) Delete o banco de dados existente (geralmente `db.sqlite3`)  
2) Rode as migrações novamente:  
   `python manage.py makemigrations`  
   `python manage.py migrate`  
3) Crie novamente o superusuário:  
   `python manage.py createsuperuser`  
4) Rode o servidor:  
   `python manage.py runserver`
![image](https://github.com/user-attachments/assets/325c5b1f-bed6-4fb6-8a1d-70ff5f575ca7)
![image](https://github.com/user-attachments/assets/f4777e15-43ee-468b-9047-0d240427fe66)
