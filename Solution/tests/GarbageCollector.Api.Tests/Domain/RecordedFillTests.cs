using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Tests;
public class RecordedFillTests
{
    [Theory]
    [InlineData("0", 0)] [InlineData("100", 100)] [InlineData("52.5", 52.5)]
    [InlineData(" 40 ", 40)]
    public void ParsesPercentages(string value, double expected) =>
        Assert.Equal(expected, RecordedFill.ParsePercentage(value));

    [Theory]
    [InlineData(null)] [InlineData("")] [InlineData("NaN")] [InlineData("Infinity")]
    [InlineData("-1")] [InlineData("100.1")] [InlineData("50%")] [InlineData("52,5")]
    public void InvalidPercentagesAreUnknownInsteadOfZero(string? value) =>
        Assert.Null(RecordedFill.ParsePercentage(value));

    [Fact]
    public void ParsingIsIndependentOfServerCulture()
    {
        var original = CultureInfo.CurrentCulture;
        try {
            CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("de-DE");
            Assert.Equal(52.5, RecordedFill.ParsePercentage("52.5"));
            Assert.Null(RecordedFill.ParsePercentage("52,5"));
        }
        finally { CultureInfo.CurrentCulture = original; }
    }
    [Fact]
    public void ParsingPreservesCategoricalOverflowAndUnknownValues()
    {
        Assert.Equal(new RecordedFill(null, true), RecordedFill.Parse(" OVERFULL "));
        Assert.Equal(new RecordedFill(null, false), RecordedFill.Parse("bad"));
        Assert.Equal(new RecordedFill(0, false), RecordedFill.Parse("0"));
    }
}
