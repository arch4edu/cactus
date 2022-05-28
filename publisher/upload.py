if __name__ == '__main__':
    import logging
    import shutil
    import socket
    from pathlib import Path
    from tornado.log import enable_pretty_logging
    from tornado.options import options

    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    repository = Path('repository')
    packages = Path('.').glob('*.pkg.tar.zst')
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 9900))

    for package in packages:
        logger.info(f'Uploading {package.name}')
        shutil.copy(package.parent / f'{package.name}.sig' , repository / 'any')
        shutil.copy(package, repository / 'any')
        _, _ = s.recvfrom(1024)
