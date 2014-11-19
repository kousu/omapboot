
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>

#define DEV "/dev/ugen0.01"

int main() {
  int f = open(DEV, O_RDWR | O_NONBLOCK);
  if(f == -1) {
    perror("open");
    return -1;
  }
  char GET_ID[4] = {0x03, 0x00, 0x03, 0xF0};
  int r = write(f, GET_ID, 4);
  if(r == -1) {
    perror("write");
    return -2;
  }
  //sleep(1);
  
  unsigned char buf[1<<10];
  r = read(f, buf, 81);
  if(r == -1) {
    perror("read");
    return -3;
  }
  printf("read ASIC ID:\n");
  for(int i=0; i<81; i++) {
    printf("%02x ", buf[i]);
  }
  printf("\n");
  return 0;
}
