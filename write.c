
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>

#include <dev/usb/usb.h>

#define DEV "/dev/ugen0.01"

int main() {  
  int f = open(DEV, O_RDWR | O_NONBLOCK);
  if(f == -1) {
    perror("open");
    return -1;
  }
  
  int r;
  r = 1;
  if((ioctl(f, USB_SET_SHORT_XFER, &r)) == -1) {
    perror("ioctl: USB_SET_SHORT_XFER");
    return -1;
  }
  
  char GET_ID[4] = {0x03, 0x00, 0x03, 0xF0};
  if((write(f, GET_ID, 4)) == -1) {
    perror("write");
    return -2;
  }
  //sleep(1);
  
  unsigned char buf[1<<10];
  r = read(f, buf, sizeof(buf));
  if(r == -1) {
    perror("read");
    return -3;
  }
  printf("read ASIC ID (%d bytes):\n", r);
  for(int i=0; i<r; i++) {
    printf("%02x ", buf[i]);
  }
  printf("\n");
  return 0;
}
