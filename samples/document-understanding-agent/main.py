from src import ixp, du_modern, pretrained

def main():
    ixp.extract_validate()

    du_modern.extract_validate()
    du_modern.classify_extract_validate()

    pretrained.extract_validate()
    pretrained.classify_extract_validate()
