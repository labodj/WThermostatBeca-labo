#ifndef W_STRING_STREAM_H
#define W_STRING_STREAM_H

#include <Stream.h>
#include <algorithm>
#include <limits.h>
#include <new>

class WStringStream : public Stream {
public:
	WStringStream(const WStringStream&) = delete;
	WStringStream& operator=(const WStringStream&) = delete;
    using Print::printf;
    
	WStringStream(unsigned int maxLength) {
		this->maxLength = maxLength;
		this->string = nullptr;
		this->position = 0;
        this->_startMillis = 0;
        WStringStream::flush();
	}

	virtual ~WStringStream() override {
		if (this->string) {
			delete[] this->string;
		}
	}

    // Stream methods
    virtual int available() override {
    	return position > INT_MAX ? INT_MAX : static_cast<int>(position);
    }

    virtual int read() override {
    	if (position > 0) {
    		unsigned char c = static_cast<unsigned char>(string[0]);
    		for (unsigned int i = 1; i <= position; i++) {
    			string[i - 1] = string[i];
    		}
			position--;
    		return c;
    	}
    	return -1;
    }

    virtual int peek() override {
    	if (position > 0) {
    	    unsigned char c = static_cast<unsigned char>(string[0]);
    	    return c;
    	}
    	return -1;
    }

    virtual void flush() override {
    	this->position = 0;
        if (!string && maxLength != UINT_MAX) string = new (std::nothrow) char[maxLength + 1];
        truncated = !string;
        if (string) string[0] = '\0';
    }

    // Print methods
    virtual size_t write(uint8_t c) override {
        if (string && position < maxLength) {
    		string[position] = (char) c;
    		position++;
    		string[position] = '\0';
    		return 1;
    	} else {
                truncated = true;
		return 0;
    	}
    }

    unsigned int length() {
        return this->position;
    }

    unsigned int getMaxLength() {
    	return this->maxLength;
    }

    char charAt(int index) {
        return index >= 0 && static_cast<unsigned>(index) < position ? string[index] : '\0';
    }

    size_t printf(const char* format, ...) {
        va_list args;
        va_start(args, format);
        const size_t written = appendFormatted(args, format);
        va_end(args);
        return written;
    }

    size_t printf(const __FlashStringHelper* format, ...) {
        va_list args;
        va_start(args, format);
        const size_t written = appendFormatted(args, reinterpret_cast<PGM_P>(format));
        va_end(args);
        return written;
    }

    size_t printAndReplace(const __FlashStringHelper* format, ...) {
        va_list args;
        va_start(args, format);
        const size_t written = appendFormatted(args, reinterpret_cast<PGM_P>(format));
        va_end(args);
        return written;
    }

    bool overflowed() const { return truncated; }

    const char* c_str() {
		return string ? string : "";
    }

private:
    // Keep va_list out of the printf overload set. Some 32-bit ABIs define it as char*.
    size_t appendFormatted(va_list args, PGM_P format) {
        if (!string) return 0;
        const size_t remaining = maxLength - position;
        const int needed = vsnprintf_P(string + position, remaining + 1, format, args);
        if (needed < 0) {
            string[position] = '\0';
            truncated = true;
            return 0;
        }
        const size_t written = std::min(remaining, static_cast<size_t>(needed));
        position += written;
        if (written < static_cast<size_t>(needed)) truncated = true;
        return written;
    }

    char* string;
    unsigned int maxLength;
    unsigned int position;
    bool truncated = false;
};

#endif // W_STRING_STREAM_H
