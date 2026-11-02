#ifndef RANDGRID_PROTOCOL_H
#define RANDGRID_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define RANDGRID_STATUS_OK UINT32_C(0x20000000)
#define RANDGRID_STATUS_FAILED UINT32_C(0xe0000001)
#define RANDGRID_STATUS_UNSUPPORTED UINT32_C(0xc0000010)

struct randgrid_context {
    uint32_t tick_multiplier;
    uint64_t tick_count;
    uint32_t cookie;
    uint64_t process_id;
    uint64_t process_peb;
};

/* time_bucket is the millisecond tick count rounded to a multiple of 1024. */
void randgrid_protocol_derive(const struct randgrid_context *context,
                             uint64_t time_bucket,
                             unsigned char key[16], unsigned char nonce[16]);

/* The caller validates outer IOCTL 0x8231214c. Input/output may alias.
 * Only the observed authenticated 16-byte handshake is implemented.
 * Unknown packet sizes or commands return UNSUPPORTED with zero output_size.
 */
uint32_t randgrid_protocol_request(const struct randgrid_context *context,
                                  const unsigned char *input, size_t input_size,
                                  unsigned char *output, size_t output_capacity,
                                  size_t *output_size);

#endif
