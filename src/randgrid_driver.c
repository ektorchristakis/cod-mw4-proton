#include <ddk/ntddk.h>
#include "randgrid_protocol.h"

PVOID NTAPI PsGetProcessPeb(PEPROCESS process);

/* Diagnostic device for Wine's userspace driver host. Unknown requests fail. */
static HANDLE log_file;
static UNICODE_STRING device_link;

static char *append_text(char *out, const char *text)
{
    while (*text) *out++ = *text++;
    return out;
}

static char *append_hex(char *out, ULONG value)
{
    int shift;
    for (shift = 28; shift >= 0; shift -= 4)
        *out++ = "0123456789abcdef"[(value >> shift) & 15];
    return out;
}

static void log_request(PIO_STACK_LOCATION stack, PIRP irp)
{
    char line[1024], *out = line;
    IO_STATUS_BLOCK iosb;
    ULONG length = 0, i;
    const UCHAR *input = NULL;

    if (!log_file) return;
    out = append_text(out, "major=");
    out = append_hex(out, stack->MajorFunction);
    if (stack->MajorFunction == IRP_MJ_DEVICE_CONTROL) {
        ULONG code = stack->Parameters.DeviceIoControl.IoControlCode;
        length = stack->Parameters.DeviceIoControl.InputBufferLength;
        out = append_text(out, " ioctl=");
        out = append_hex(out, code);
        out = append_text(out, " in=");
        out = append_hex(out, length);
        out = append_text(out, " out=");
        out = append_hex(out, stack->Parameters.DeviceIoControl.OutputBufferLength);
        /* Wine marshals both forms into the driver-host process. */
        input = (code & 3) == METHOD_NEITHER
            ? stack->Parameters.DeviceIoControl.Type3InputBuffer
            : irp->AssociatedIrp.SystemBuffer;
    }
    if (input && length) {
        out = append_text(out, " input=");
        for (i = 0; i < length && i < 256; ++i) {
            *out++ = "0123456789abcdef"[input[i] >> 4];
            *out++ = "0123456789abcdef"[input[i] & 15];
        }
        if (length > 256) out = append_text(out, "...");
    }
    *out++ = '\n';
    ZwWriteFile(log_file, NULL, NULL, NULL, &iosb, line, (ULONG)(out - line), NULL, NULL);
}

static void log_result(NTSTATUS status, ULONG_PTR information, const UCHAR *buffer)
{
    char line[600], *out = line;
    IO_STATUS_BLOCK iosb;
    ULONG_PTR i;
    if (!log_file) return;
    out = append_text(out, "status=");
    out = append_hex(out, (ULONG)status);
    out = append_text(out, " bytes=");
    out = append_hex(out, (ULONG)information);
    if (buffer && information) {
        out = append_text(out, " output=");
        for (i = 0; i < information && i < 256; ++i) {
            *out++ = "0123456789abcdef"[buffer[i] >> 4];
            *out++ = "0123456789abcdef"[buffer[i] & 15];
        }
    }
    *out++ = '\n';
    ZwWriteFile(log_file, NULL, NULL, NULL, &iosb, line, (ULONG)(out - line), NULL, NULL);
}

static void log_context(const struct randgrid_context *context)
{
    char line[200], *out = line;
    IO_STATUS_BLOCK iosb;
    if (!log_file) return;
    out = append_text(out, "context pid=");
    out = append_hex(out, (ULONG)(context->process_id >> 32));
    out = append_hex(out, (ULONG)context->process_id);
    out = append_text(out, " peb=");
    out = append_hex(out, (ULONG)(context->process_peb >> 32));
    out = append_hex(out, (ULONG)context->process_peb);
    out = append_text(out, " multiplier=");
    out = append_hex(out, context->tick_multiplier);
    out = append_text(out, " ticks=");
    out = append_hex(out, (ULONG)(context->tick_count >> 32));
    out = append_hex(out, (ULONG)context->tick_count);
    out = append_text(out, " cookie=");
    out = append_hex(out, context->cookie);
    *out++ = '\n';
    ZwWriteFile(log_file, NULL, NULL, NULL, &iosb, line, (ULONG)(out - line), NULL, NULL);
}

static NTSTATUS dispatch(PDEVICE_OBJECT device, PIRP irp)
{
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(irp);
    NTSTATUS status = STATUS_INVALID_DEVICE_REQUEST;
    size_t information = 0;
    (void)device;
    log_request(stack, irp);
    switch (stack->MajorFunction) {
    case IRP_MJ_CREATE:
    case IRP_MJ_CLEANUP:
    case IRP_MJ_CLOSE:
        status = STATUS_SUCCESS;
        break;
    case IRP_MJ_DEVICE_CONTROL:
        if (stack->Parameters.DeviceIoControl.IoControlCode == 0x8231214c) {
            /* Wine exposes the same shared data at its userspace alias and
             * attributes these process APIs to the client sending this IRP. */
            const volatile UCHAR *shared = (const volatile UCHAR *)(ULONG_PTR)0x7ffe0000;
            struct randgrid_context context;
            context.tick_multiplier = *(const volatile ULONG *)(shared + 4);
            context.tick_count = *(const volatile ULONGLONG *)(shared + 0x320);
            context.cookie = *(const volatile ULONG *)(shared + 0x330);
            context.process_id = (ULONG_PTR)PsGetCurrentProcessId();
            context.process_peb = (ULONG_PTR)PsGetProcessPeb(IoGetCurrentProcess());
            log_context(&context);
            status = (NTSTATUS)randgrid_protocol_request(&context,
                irp->AssociatedIrp.SystemBuffer,
                stack->Parameters.DeviceIoControl.InputBufferLength,
                irp->AssociatedIrp.SystemBuffer,
                stack->Parameters.DeviceIoControl.OutputBufferLength, &information);
        }
        break;
    }
    log_result(status, information, irp->AssociatedIrp.SystemBuffer);
    irp->IoStatus.Status = status;
    irp->IoStatus.Information = information;
    IoCompleteRequest(irp, IO_NO_INCREMENT);
    return status;
}

static void unload(PDRIVER_OBJECT driver)
{
    IoDeleteSymbolicLink(&device_link);
    if (driver->DeviceObject) IoDeleteDevice(driver->DeviceObject);
    if (log_file) ZwClose(log_file);
    log_file = NULL;
}

NTSTATUS NTAPI DriverEntry(PDRIVER_OBJECT driver, PUNICODE_STRING registry_path)
{
    UNICODE_STRING name, path;
    OBJECT_ATTRIBUTES attributes;
    IO_STATUS_BLOCK iosb;
    PDEVICE_OBJECT device;
    NTSTATUS status;
    unsigned int i;
    (void)registry_path;

    RtlInitUnicodeString(&path, L"\\??\\C:\\randgrid-wine.log");
    InitializeObjectAttributes(&attributes, &path, OBJ_CASE_INSENSITIVE | OBJ_KERNEL_HANDLE,
                               NULL, NULL);
    status = ZwCreateFile(&log_file, FILE_APPEND_DATA | SYNCHRONIZE, &attributes, &iosb,
                          NULL, FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ, FILE_OVERWRITE_IF,
                          FILE_SYNCHRONOUS_IO_NONALERT | FILE_NON_DIRECTORY_FILE, NULL, 0);
    if (!NT_SUCCESS(status)) return status;
    RtlInitUnicodeString(&name, L"\\Device\\Randgrid");
    RtlInitUnicodeString(&device_link, L"\\DosDevices\\Randgrid");
    for (i = 0; i <= IRP_MJ_MAXIMUM_FUNCTION; ++i) driver->MajorFunction[i] = dispatch;
    driver->DriverUnload = unload;
    status = IoCreateDevice(driver, 0, &name, FILE_DEVICE_UNKNOWN, FILE_DEVICE_SECURE_OPEN,
                            FALSE, &device);
    if (!NT_SUCCESS(status)) {
        ZwClose(log_file);
        log_file = NULL;
        return status;
    }
    status = IoCreateSymbolicLink(&device_link, &name);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(device);
        ZwClose(log_file);
        log_file = NULL;
        return status;
    }
    device->Flags &= ~DO_DEVICE_INITIALIZING;
    return STATUS_SUCCESS;
}
