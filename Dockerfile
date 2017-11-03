FROM python:2

WORKDIR /opt/helga

COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install .

CMD ["helga","--settings=dev-settings.py"]
