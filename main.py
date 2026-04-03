import sys

from scheduler import run_lab01_from_image


def main():
    if len(sys.argv) > 1:
        source_path = sys.argv[1].strip()
    else:
        source_path = input("Enter FAT32 image path (.img): ").strip()

    if not source_path:
        print("No image path provided.")
        return

    run_lab01_from_image(source_path)


if __name__ == "__main__":
    main()
