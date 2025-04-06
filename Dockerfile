FROM python:3.12

WORKDIR /app

COPY src .

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "main.py" ]