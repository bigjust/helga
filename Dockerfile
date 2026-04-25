FROM python:3

ADD . /code
WORKDIR /code

RUN pip install .

# Copy settings file to a location that will be available
COPY settings_docker.py /etc/helga_settings.py

ENTRYPOINT ["/usr/local/bin/helga"]
CMD ["--settings=/etc/helga_settings.py"]
