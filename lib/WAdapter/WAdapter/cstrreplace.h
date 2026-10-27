
#ifndef CSTRREPLACE_H
#define CSTRREPLACE_H

#include <string.h>
#include <stdlib.h>
#include <stdint.h>

char * cstrReplace(
    char const * const original, 
    char const * const pattern, 
    char const * const replacement
) {
  if (!original || !pattern || !replacement) return NULL;
  size_t const replen = strlen(replacement);
  size_t const patlen = strlen(pattern);
  size_t const orilen = strlen(original);

  if (patlen == 0) {
    char* copy = (char*)malloc(orilen + 1);
    if (copy) memcpy(copy, original, orilen + 1);
    return copy;
  }

  size_t patcnt = 0;
  const char * oriptr;
  const char * patloc;

  // find how many times the pattern occurs in the original string
  for (oriptr = original; (patloc = strstr(oriptr, pattern)); oriptr = patloc + patlen)
  {
    patcnt++;
  }

  {
    // allocate memory for the new string
    size_t const unchanged = orilen - patcnt * patlen;
    if (patcnt && replen > (SIZE_MAX - unchanged - 1) / patcnt) return NULL;
    size_t const retlen = unchanged + patcnt * replen;
    char * const returned = (char *) malloc( sizeof(char) * (retlen + 1) );

    if (returned != NULL)
    {
      // copy the original string, 
      // replacing all the instances of the pattern
      char * retptr = returned;
      for (oriptr = original; (patloc = strstr(oriptr, pattern)); oriptr = patloc + patlen)
      {
        size_t const skplen = patloc - oriptr;
        // copy the section until the occurence of the pattern
        memcpy(retptr, oriptr, skplen);
        retptr += skplen;
        // copy the replacement 
        memcpy(retptr, replacement, replen);
        retptr += replen;
      }
      // copy the rest of the string.
      memcpy(retptr, oriptr, orilen - (oriptr - original) + 1);
    }
    return returned;
  }
}
#endif