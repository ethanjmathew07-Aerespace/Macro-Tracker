try:
    from .simulator import main
except ImportError:
    from simulator import main


if __name__ == "__main__":
    main()
