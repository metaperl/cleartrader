package Local::Log;

use Moose;

use Log::Log4perl;

BEGIN {
    my $cfg = <<EOCFG;
log4j.rootLogger=DEBUG, stdout, R
log4j.appender.stdout=org.apache.log4j.ConsoleAppender
log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
log4j.appender.stdout.layout.ConversionPattern=%5p (%F:%L) - %m%n
log4j.appender.R=org.apache.log4j.RollingFileAppender
log4j.appender.R.File=local.log
log4j.appender.R.layout=org.apache.log4j.PatternLayout
log4j.appender.R.layout.ConversionPattern=%p %c - %m%n
EOCFG
    Log::Log4perl->init( \$cfg );
}

with 'MooseX::Log::Log4perl';

# http://www.cpan.org/authors/id/V/VK/VKHERA/logrotate-1.06
use Fcntl;
sub rotate {
    my ( $file, $howmany ) = @_;
    my ($cur);

    $howmany ||= 99;

    unlink( "$file.$howmany", "$file.$howmany.gz" );    # remove topmost one.

    for ( $cur = $howmany ; $cur > 0 ; $cur-- ) {
        my $prev = $cur - 1;
        rename( "$file.$prev",    "$file.$cur" )    if ( -f "$file.$prev" );
        rename( "$file.$prev.gz", "$file.$cur.gz" ) if ( -f "$file.$prev.gz" );
    }

    rename( "$file", "$file.0" );                       # move original one

    # create the new one!
    my $fh = new IO::File $file, O_WRONLY | O_CREAT, 0644;
    $fh->close();
}

1;
