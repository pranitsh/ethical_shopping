from . import runner, scraper

if __name__ == "__main__":
    import doctest
    doctest.testmod(runner)
    doctest.testmod(scraper)
