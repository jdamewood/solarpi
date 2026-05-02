#define _XOPEN_SOURCE 700
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <time.h>
#include <errno.h>
#include <sys/select.h>

#include <cjson/cJSON.h>
#include <systemd/sd-daemon.h>
#include <stdint.h>

#define HOST "192.168.1.164"
#define PORT 5005
#define CSV_FILE "sensor_log.csv"
#define JSON_LOG "sensor_log.json"
#define BUFFER_SIZE 8192

char host[64] = HOST;
int port = PORT;
char csv_file[128] = CSV_FILE;
char json_file[128] = JSON_LOG;

const char *csv_header[] = {
    "timestamp",
    "ina45_v", "ina45_i", "ina41_v", "ina41_i", "ina44_v", "ina44_i",
    "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1",
    "tsl39_lux", "tsl29_lux",
    "bme_temp", "bme_hum", "bme_press", 
    "wifi_rssi", 
    "read_time"  // ← Column 17 ADDED!
};

const int csv_header_count = sizeof(csv_header) / sizeof(csv_header[0]);

const char *int_fields[] = {
    "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1", 
    "wifi_rssi"  // read_time = float, NOT int
};
const int int_fields_count = sizeof(int_fields) / sizeof(int_fields[0]);

int is_int_field(const char *field) {
    for (int i = 0; i < int_fields_count; i++) {
        if (strcmp(field, int_fields[i]) == 0) return 1;
    }
    return 0;
}

time_t parse_timestamp(const char *ts_str) {
    struct tm tm = {0};
    if (strptime(ts_str, "%Y-%m-%d %H:%M:%S", &tm) == NULL) {
        fprintf(stderr, "Timestamp parsing error for '%s'\n", ts_str);
        return (time_t)-1;
    }
    return mktime(&tm);
}

// FIXED: Pass pointer to avoid scope issues
int check_timestamp(const char *ts_str, time_t *last_ts_ptr) {
    time_t current_ts = parse_timestamp(ts_str);
    if (current_ts == (time_t)-1) return 0;
    
    if (*last_ts_ptr != 0) {
        if (difftime(current_ts, *last_ts_ptr) < 0) {
            fprintf(stderr, "*** Timestamp mismatch: %s < last ***\n", ts_str);
            return 0;
        }
        if (difftime(current_ts, *last_ts_ptr) > 3600) {
            fprintf(stderr, "*** Timestamp jump detected: %s ***\n", ts_str);
        }
    }
    *last_ts_ptr = current_ts;
    return 1;
}

void format_value(const char *field, const char *val, char *out_buf, size_t out_size) {
    if (val == NULL || strcmp(val, "") == 0 || strcmp(val, "NULL") == 0) {
        out_buf[0] = '\0';
        return;
    }
    if (is_int_field(field)) {
        double dval = atof(val);
        snprintf(out_buf, out_size, "%d", (int)dval);
    } else {
        double dval = atof(val);
        snprintf(out_buf, out_size, "%.4f", dval);
    }
}

void append_to_csv(const char *line) {
    FILE *fp;
    int write_header = 0;
    fp = fopen(csv_file, "r");
    if (fp == NULL) {
        write_header = 1;
    } else {
        fseek(fp, 0, SEEK_END);
        if (ftell(fp) == 0) write_header = 1;
        fclose(fp);
    }
    fp = fopen(csv_file, "a");
    if (!fp) {
        fprintf(stderr, "Cannot open CSV for writing\n");
        return;
    }
    if (write_header) {
        for (int i = 0; i < csv_header_count; i++) {
            fprintf(fp, "%s", csv_header[i]);
            if (i < csv_header_count - 1) fprintf(fp, ",");
        }
        fprintf(fp, "\n");
    }
    fprintf(fp, "%s\n", line);
    fclose(fp);
}

void append_to_json_log(const char *json_str) {
    FILE *fp = fopen(json_file, "a");
    if (!fp) {
        fprintf(stderr, "Cannot open JSON log for writing\n");
        return;
    }
    fprintf(fp, "%s\n", json_str);
    fclose(fp);
}

void print_usage(const char *progname, int notify_interval_sec) {
    fprintf(stderr,
        "Usage: %s -h <host:port> -l <csv_log_file> -j <json_log_file> -t <interval_sec>\n"
        "Defaults:\n"
        "  host=%s:%d\n"
        "  csv_log=%s\n"
        "  json_log=%s\n"
        "  interval_sec=%d\n",
        progname, host, port, csv_file, json_file, notify_interval_sec);
}

int main(int argc, char *argv[]) {
    // FIXED: Now local to main()
    time_t last_timestamp = 0;
    
    int opt;
    uint64_t watchdog_usec = 0;
    int watchdog_enabled = sd_watchdog_enabled(0, &watchdog_usec);
    int notify_interval_sec = 20;

    while ((opt = getopt(argc, argv, "h:l:j:t:")) != -1) {
        switch (opt) {
            case 'h': {
                char *colon = strchr(optarg, ':');
                if (!colon) {
                    fprintf(stderr, "Invalid host format. Must be IP:port\n");
                    print_usage(argv[0], notify_interval_sec);
                    return 1;
                }
                size_t ip_len = colon - optarg;
                if (ip_len >= sizeof(host)) ip_len = sizeof(host) - 1;
                strncpy(host, optarg, ip_len);
                host[ip_len] = '\0';
                port = atoi(colon + 1);
                break;
            }
            case 'l':
                strncpy(csv_file, optarg, sizeof(csv_file) - 1);
                csv_file[sizeof(csv_file) - 1] = '\0';
                break;
            case 'j':
                strncpy(json_file, optarg, sizeof(json_file) - 1);
                json_file[sizeof(json_file) - 1] = '\0';
                break;
            case 't':
                notify_interval_sec = atoi(optarg);
                if (notify_interval_sec < 1) notify_interval_sec = 1;
                break;
            default:
                print_usage(argv[0], notify_interval_sec);
                return 1;
        }
    }

    if (watchdog_enabled && watchdog_usec > 0) {
        int half_watchdog_sec = (int)(watchdog_usec / 1000000 / 2);
        if (half_watchdog_sec < notify_interval_sec) {
            notify_interval_sec = half_watchdog_sec;
        }
    }

    sd_notify(0, "READY=1");

    int sock = -1;
    int fd_count = sd_listen_fds(0);
    if (fd_count == 1) {
        sock = SD_LISTEN_FDS_START;
    }

    while (1) {
        if (sock == -1) {
            sock = socket(AF_INET, SOCK_STREAM, 0);
            if (sock < 0) {
                perror("Socket creation failed");
                sleep(60);
                continue;
            }
            struct sockaddr_in serv_addr = {0};
            serv_addr.sin_family = AF_INET;
            serv_addr.sin_port = htons(port);
            if (inet_pton(AF_INET, host, &serv_addr.sin_addr) <= 0) {
                fprintf(stderr, "Invalid address/ Address not supported\n");
                close(sock);
                sock = -1;
                sleep(60);
                continue;
            }
            fcntl(sock, F_SETFL, O_NONBLOCK);
            if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
                if (errno != EINPROGRESS) {
                    perror("Connect error");
                    close(sock);
                    sock = -1;
                    sleep(60);
                    continue;
                }
            }
            fd_set fdset;
            struct timeval tv;
            FD_ZERO(&fdset);
            FD_SET(sock, &fdset);
            tv.tv_sec = 15;
            tv.tv_usec = 0;
            if (select(sock + 1, NULL, &fdset, NULL, &tv) <= 0) {
                fprintf(stderr, "Connection timeout\n");
                close(sock);
                sock = -1;
                sleep(60);
                continue;
            }
            int so_error;
            socklen_t len = sizeof so_error;
            getsockopt(sock, SOL_SOCKET, SO_ERROR, &so_error, &len);
            if (so_error != 0) {
                fprintf(stderr, "Socket error %d\n", so_error);
                close(sock);
                sock = -1;
                sleep(60);
                continue;
            }
            fcntl(sock, F_SETFL, fcntl(sock, F_GETFL, 0) & (~O_NONBLOCK));
        }

        if (send(sock, "go", 2, 0) != 2) {
            fprintf(stderr, "Send error\n");
            close(sock);
            sock = -1;
            sleep(60);
            continue;
        }

        char recv_buf[BUFFER_SIZE] = {0};
        int total_received = 0;
        int n;
        while ((n = recv(sock, recv_buf + total_received, BUFFER_SIZE - total_received - 1, 0)) > 0) {
            total_received += n;
            if (total_received >= BUFFER_SIZE - 1)
                break;
        }
        if (n < 0) {
            perror("Receive error");
            close(sock);
            sock = -1;
            sleep(60);
            continue;
        }
        recv_buf[total_received] = '\0';

        if (total_received == 0 || strlen(recv_buf) == 0) {
            fprintf(stderr, "Empty JSON received, closing socket and skipping\n");
            close(sock);
            sock = -1;
            sleep(notify_interval_sec);
            continue;
        }

        cJSON *json = cJSON_Parse(recv_buf);
        if (!json) {
            fprintf(stderr, "JSON parsing error: %s\n", cJSON_GetErrorPtr());
            close(sock);
            sock = -1;
            sleep(notify_interval_sec);
            continue;
        }

        cJSON *ts_item = cJSON_GetObjectItemCaseSensitive(json, "timestamp");
        if (!cJSON_IsString(ts_item) || !ts_item->valuestring) {
            fprintf(stderr, "Timestamp missing or invalid\n");
            cJSON_Delete(json);
            sleep(notify_interval_sec);
            continue;
        }
        
        // FIXED: Pass pointer to last_timestamp
        if (!check_timestamp(ts_item->valuestring, &last_timestamp)) {
            fprintf(stderr, "Skipping entry due to timestamp issue: %s\n", ts_item->valuestring);
            cJSON_Delete(json);
            sleep(notify_interval_sec);
            continue;
        }

        append_to_json_log(recv_buf);

        char csv_line[2048] = {0};
        size_t offset = 0;
        for (int i = 0; i < csv_header_count; i++) {
            const char *field = csv_header[i];
            cJSON *val_item = cJSON_GetObjectItemCaseSensitive(json, field);
            const char *val_str = "";
            if (val_item) {
                if (cJSON_IsString(val_item)) {
                    val_str = val_item->valuestring;
                } else if (cJSON_IsNumber(val_item)) {
                    static char numbuf[64];
                    if (is_int_field(field)) {
                        snprintf(numbuf, sizeof(numbuf), "%d", (int)(val_item->valuedouble));
                    } else {
                        snprintf(numbuf, sizeof(numbuf), "%.4f", val_item->valuedouble);
                    }
                    val_str = numbuf;
                }
            }
            if (i == 0) {
                offset += snprintf(csv_line + offset, sizeof(csv_line) - offset, "%s", val_str);
            } else {
                char formatted[64];
                format_value(field, val_str, formatted, sizeof(formatted));
                offset += snprintf(csv_line + offset, sizeof(csv_line) - offset, ",%s", formatted);
            }
        }
        append_to_csv(csv_line);

        printf("Logged: %s\n", csv_line);

        cJSON_Delete(json);

        if (watchdog_enabled) {
            sd_notify(0, "WATCHDOG=1");
        }

        sleep(notify_interval_sec);
    }

    return 0;
}

