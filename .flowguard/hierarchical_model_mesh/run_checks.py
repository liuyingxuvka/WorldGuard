from model import run_model
from flowguard.map.runner import run_owner

def main():
    return run_model()

if __name__ == "__main__":
    raise SystemExit(run_owner(main))
