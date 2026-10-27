#ifndef W_STRING_STREAM_H
#define W_STRING_STREAM_H

#include <Stream.h>
#include <limits.h>

class WStringStream : public Stream {
public:
	WStringStream(const WStringStream&) = delete;
	WStringStream& operator=(const WStringStream&) = delete;
    using Print::printf;
    
	WStringStream(unsigned int maxLength) {
		this->maxLength = maxLength;
		this->string = new char[maxLength + 1];
		this->position = 0;
        this->_startMillis = 0;
        this->string[0] = '\0';
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
        truncated = false;
    	this->string[0] = '\0';
    }

    // Print methods
    virtual size_t write(uint8_t c) override {
    	if (position < maxLength) {
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
    	return this->string[index];
    }

	size_t printf(const char *format, va_list args) {
		if (position >= maxLength) { truncated = true; return 0; }
		const size_t remaining = maxLength - position;
		const int needed = vsnprintf(&string[position], remaining + 1, format, args);
		if (needed < 0) return 0;
		if (static_cast<size_t>(needed) > remaining) truncated = true;
        const size_t written = static_cast<size_t>(needed) > remaining ? remaining : static_cast<size_t>(needed);
		position += written;
		return written;	
	}
	size_t printf(const char *format, ...) {
		va_list args;
		va_start(args, format);
		size_t len = printf(format, args);
		va_end(args);
		return len;
	}
	size_t printf(const __FlashStringHelper *format, va_list args) {
		char buf[1024];
		size_t size = sizeof buf;
		PGM_P p = reinterpret_cast<PGM_P>(format);
		char c;
		unsigned int pos=0;
		for (; pos < size-1 && (c = pgm_read_byte(p++)) != 0; pos++) {
				buf[pos]=c;
		}
		buf[pos]='\0';
		size_t len = printf(buf, args);
		return len;
	}
	
	size_t printf(const __FlashStringHelper *format, ...) {
		va_list args;
		va_start(args, format);
		size_t len = printf(format, args);
		va_end(args);
		return len;
	}

	size_t printAndReplace(const __FlashStringHelper *format, ...) {
		va_list args;
		va_start(args, format);
		size_t len = printf(format, args);
		va_end(args);
		return len;
	}

    bool overflowed() const { return truncated; }

    const char* c_str() {
		return this->string;
    }

private:
    char* string;
    unsigned int maxLength;
    unsigned int position;
    bool truncated = false;
};

#endif // W_STRING_STREAM_H
