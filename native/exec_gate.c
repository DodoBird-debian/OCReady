/* Start an OCR engine only after the parent has attached its worker scope. */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char token;
    if (argc < 4 || read(STDIN_FILENO, &token, 1) != 1) return 125;
    /* Retain the cgroup until the app has read its final OOM evidence. */
    prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0);
    pid_t engine = fork();
    if (engine < 0) return 125;
    if (engine == 0) {
        FILE *score = fopen("/proc/self/oom_score_adj", "w");
        if (score) { fputs("1000", score); fclose(score); }
        int input = open("/dev/null", O_RDONLY);
        if (input >= 0) {
            if (dup2(input, STDIN_FILENO) < 0) _exit(125);
            close(input);
        }
        execvp(argv[3], argv + 3);
        perror("OCReady could not start the OCR engine");
        _exit(127);
    }
    int status;
    if (waitpid(engine, &status, 0) < 0) return 125;
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
    FILE *result = fopen(argv[1], "w");
    if (!result) { perror("OCReady worker status"); return 125; }
    fprintf(result, "%d\n", code);
    fclose(result);
    /* The app closes this pipe after observing the result and cgroup counters. */
    (void)read(STDIN_FILENO, &token, 1);
    return code < 0 ? 128 - code : code;
}
