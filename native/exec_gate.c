/* Start an OCR engine only after the parent has attached its worker scope. */
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char token;
    if (argc < 2 || read(STDIN_FILENO, &token, 1) != 1) return 125;
    int input = open("/dev/null", O_RDONLY);
    if (input >= 0) {
        if (dup2(input, STDIN_FILENO) < 0) return 125;
        close(input);
    }
    execvp(argv[1], argv + 1);
    perror("OCReady could not start the OCR engine");
    return 127;
}
