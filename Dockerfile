FROM python:3

ADD . /code
WORKDIR /code

RUN pip install .

ENTRYPOINT ["/usr/local/bin/helga"]
CMD ["--settings=settings_docker"]
