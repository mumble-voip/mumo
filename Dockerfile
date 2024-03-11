FROM python:3

RUN pip install --no-cache-dir zeroc-ice

COPY entrypoint.sh /entrypoint.sh
COPY . /mumo

RUN chmod +x /entrypoint.sh && \
    ln -sf /dev/stdout /mumo/mumo.log

VOLUME ["/data"]

WORKDIR /mumo
ENTRYPOINT [ "/entrypoint.sh" ]

CMD ["/mumo/mumo.py", "--ini", "/data/mumo.ini"]
